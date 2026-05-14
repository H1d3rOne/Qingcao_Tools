<template>
  <div class="quark-files-page files-container">
    <el-container>
      <!-- 顶部导航栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button @click="goBack" :disabled="!canGoBack">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
        </div>
        <div class="header-right">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索文件"
            style="width: 200px; margin-right: 10px"
            @keyup.enter="handleSearch"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleUpload">
            <el-icon><Upload /></el-icon>
            上传
          </el-button>
          <el-button @click="handleCreateFolder">
            <el-icon><FolderAdd /></el-icon>
            新建文件夹
          </el-button>
          <el-button @click="loadFiles" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <div class="user-info" v-if="userInfo">
            <img v-if="userInfo.avatar" :src="userInfo.avatar" class="user-avatar" alt="avatar" />
            <el-icon v-else class="user-avatar-placeholder"><User /></el-icon>
            <div class="user-details">
              <span class="user-name">
                {{ userInfo.nickname || userInfo.name || '用户' }}
                <el-tag v-if="userInfo.vip_name" size="small" type="warning" style="margin-left: 5px">{{ userInfo.vip_name }}</el-tag>
              </span>
              <div class="user-storage">
                <span>{{ formatSize(storageInfo.used) }} / {{ formatSize(storageInfo.total) }}</span>
              </div>
            </div>
          </div>
          <el-dropdown @command="handleCommand">
            <el-button>
              <el-icon><More /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="storage">
                  <el-icon><PieChart /></el-icon>
                  存储空间: {{ formatSize(storageInfo.used) }} / {{ formatSize(storageInfo.total) }}
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 分享链接转存/下载区域 -->
      <div class="share-link-section">
        <div class="share-link-input">
          <el-input 
            v-model="shareLinkInput" 
            placeholder="输入分享链接（如：https://pan.quark.cn/s/xxxxxxxx）" 
            clearable
            @keyup.enter="parseShareLink"
          >
            <template #prepend>
              <el-icon><Link /></el-icon>
              <span style="margin-left: 5px">分享链接</span>
            </template>
          </el-input>
          <el-input 
            v-model="shareLinkPasscode" 
            placeholder="提取码（如有）" 
            style="width: 150px; margin-left: 10px"
            clearable
          />
        </div>
        <div class="share-link-actions">
          <el-button type="primary" @click="handleTransferShare" :loading="transferLoading">
            <el-icon><FolderAdd /></el-icon>
            转存
          </el-button>
          <el-button type="success" @click="handleDownloadShare" :loading="downloadShareLoading">
            <el-icon><Download /></el-icon>
            下载
          </el-button>
        </div>
      </div>

      <!-- 主内容区 -->
      <el-main 
        class="main" 
        :class="{ 'is-dragging': isMainDragging }"
        @drop.prevent="handleMainDrop"
        @dragover.prevent="handleMainDragOver"
        @dragleave.prevent="handleMainDragLeave"
      >
        <!-- 拖拽遮罩 -->
        <div v-if="isMainDragging" class="drag-overlay">
          <div class="drag-overlay-content">
            <el-icon :size="48" style="color: rgb(var(--quark-primary-rgb))"><Upload /></el-icon>
            <p>释放文件以上传到当前文件夹</p>
          </div>
        </div>
        
        <!-- 面包屑导航 -->
        <div class="breadcrumb-container">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item v-for="(item, index) in pathList" :key="index" @click="navigateTo(index)">
              {{ item.name }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <!-- 工具栏 -->
        <div class="toolbar" v-if="selectedFiles.length > 0">
          <span class="selected-info">已选择 {{ selectedFiles.length }} 项</span>
          <el-button size="small" @click="handleBatchDownload">下载</el-button>
          <el-button size="small" @click="handleBatchMove">移动</el-button>
          <el-button size="small" type="success" @click="handleBatchShare">分享</el-button>
          <el-button v-if="selectedFiles.length === 1" size="small" @click="handleBatchRename">重命名</el-button>
          <el-button size="small" type="danger" @click="handleBatchDelete">删除</el-button>
          <el-button size="small" @click="clearSelection">取消选择</el-button>
        </div>

        <div class="file-list-hint">
          <el-icon><Upload /></el-icon>
          <span>可将文件或文件夹拖拽到此文件列表区域上传，也可直接在此页面粘贴上传。</span>
        </div>

        <!-- 文件列表 -->
        <el-table
          :data="sortedFileList"
          style="width: 100%"
          @row-click="handleRowClick"
          @selection-change="handleSelectionChange"
          v-loading="loading"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="name" label="文件名" min-width="300">
            <template #header>
              <div class="sortable-header">
                <span>文件名</span>
                <div class="sort-buttons">
                  <el-button 
                    :class="{ 'is-active': nameSortOrder === 'asc' }" 
                    @click.stop="toggleNameSort('asc')"
                  >
                    <el-icon><CaretTop /></el-icon>
                  </el-button>
                  <el-button 
                    :class="{ 'is-active': nameSortOrder === 'desc' }" 
                    @click.stop="toggleNameSort('desc')"
                  >
                    <el-icon><CaretBottom /></el-icon>
                  </el-button>
                </div>
              </div>
            </template>
            <template #default="{ row }">
              <div class="file-name-cell" :class="{ 'clickable': row.file_type === 0 }">
                <el-icon :class="getFileIconClass(row)" :style="{ color: getFileIconColor(row) }">
                  <component :is="getFileIcon(row)" />
                </el-icon>
                <span class="file-name">{{ row.file_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="size" label="大小" width="120">
            <template #default="{ row }">
              <span :class="{ 'folder-size': row.file_type === 0 }">
                {{ row.file_type === 0 ? formatFolderSize(row.dir_size) : formatSize(row.size) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="modified" label="修改时间" width="180">
            <template #header>
              <div class="sortable-header">
                <span>修改时间</span>
                <div class="sort-buttons">
                  <el-button 
                    :class="{ 'is-active': timeSortOrder === 'asc' }" 
                    @click.stop="toggleTimeSort('asc')"
                  >
                    <el-icon><CaretTop /></el-icon>
                  </el-button>
                  <el-button 
                    :class="{ 'is-active': timeSortOrder === 'desc' }" 
                    @click.stop="toggleTimeSort('desc')"
                  >
                    <el-icon><CaretBottom /></el-icon>
                  </el-button>
                </div>
              </div>
            </template>
            <template #default="{ row }">
              {{ formatDateTime(row.updated_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button-group>
                <el-button link type="primary" size="small" @click.stop="handleDownload(row)">
                  下载
                </el-button>
                <el-button link type="primary" size="small" @click.stop="handleMove(row)">
                  移动
                </el-button>
                <el-button link type="success" size="small" @click.stop="handleShare(row)">
                  分享
                </el-button>
                <el-button link type="primary" size="small" @click.stop="handleRename(row)">
                  重命名
                </el-button>
                <el-button link type="danger" size="small" @click.stop="handleDelete(row)">
                  删除
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!loading && fileList.length === 0" description="暂无文件" />
      </el-main>

      <!-- 底部状态栏 -->
      <el-footer class="footer">
        <div class="footer-left">
          <span>共 {{ fileList.length }} 项</span>
        </div>
        <div class="footer-right">
          <span v-if="storageInfo">
            已用 {{ formatSize(storageInfo.used) }} / {{ formatSize(storageInfo.total) }}
          </span>
          <el-progress
            v-if="storageInfo"
            :percentage="storagePercentage"
            :stroke-width="6"
            style="width: 120px; margin-left: 10px"
          />
        </div>
      </el-footer>
    </el-container>

    <!-- 存储空间对话框 -->
    <el-dialog v-model="storageDialogVisible" title="存储空间" width="400px">
      <div class="storage-info" v-if="storageInfo">
        <el-progress
          type="dashboard"
          :percentage="storagePercentage"
          :width="150"
        >
          <template #default>
            <span class="storage-text">{{ formatSize(storageInfo.used) }}</span>
            <span class="storage-total">/ {{ formatSize(storageInfo.total) }}</span>
          </template>
        </el-progress>
        <div class="storage-detail">
          <p>已使用: {{ formatSize(storageInfo.used) }}</p>
          <p>总容量: {{ formatSize(storageInfo.total) }}</p>
          <p>剩余: {{ formatSize(storageInfo.total - storageInfo.used) }}</p>
        </div>
      </div>
    </el-dialog>

    <!-- 移动文件对话框 -->
    <el-dialog v-model="moveDialogVisible" title="移动到" width="600px">
      <div class="move-dialog-content">
        <el-alert v-if="moveFileNames.length > 0" type="info" :closable="false" style="margin-bottom: 15px">
          <template #title>
            <span>将移动 {{ moveFileNames.length }} 个项目：</span>
            <span v-for="(name, idx) in moveFileNames.slice(0, 3)" :key="idx">
              "{{ name }}"{{ idx < Math.min(moveFileNames.length, 3) - 1 ? '、' : '' }}
            </span>
            <span v-if="moveFileNames.length > 3">等 {{ moveFileNames.length }} 个项目</span>
          </template>
        </el-alert>
        
        <el-tree
          :data="folderTree"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          highlight-current
          :expand-on-click-node="true"
          :default-expanded-keys="['0']"
          @node-click="handleMoveTargetSelect"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-icon style="margin-right: 5px; color: rgb(var(--quark-primary-rgb))"><Folder /></el-icon>
              <span>{{ data.name }}</span>
              <el-tag v-if="data.id === currentFolderId" size="small" type="warning" style="margin-left: 8px">当前目录</el-tag>
            </span>
          </template>
        </el-tree>
      </div>
      <template #footer>
        <el-button @click="moveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmMove" :disabled="!moveTargetId || moveTargetId === currentFolderId">确定移动</el-button>
      </template>
    </el-dialog>

    <!-- 分享对话框 -->
    <el-dialog v-model="shareDialogVisible" title="创建分享" width="500px">
      <div class="share-options">
        <el-form label-width="80px">
          <el-form-item label="有效期">
            <el-select v-model="shareExpireDays" placeholder="选择有效期">
              <el-option label="永久有效" :value="0" />
              <el-option label="1天" :value="1" />
              <el-option label="7天" :value="7" />
              <el-option label="30天" :value="30" />
            </el-select>
          </el-form-item>
          <el-form-item label="提取码">
            <el-input v-model="sharePassword" placeholder="留空则无提取码" style="width: 150px" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="shareDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createShare" :loading="shareLoading">创建分享</el-button>
      </template>
    </el-dialog>

    <!-- 分享成功对话框 -->
    <el-dialog v-model="shareResultVisible" title="分享成功" width="500px">
      <div class="share-success" v-if="shareInfo">
        <div class="share-link-box">
          <el-input v-model="shareInfo.share_url" readonly>
            <template #prepend>链接</template>
            <template #append>
              <el-button @click="handleCopyLink">复制</el-button>
            </template>
          </el-input>
          <div v-if="shareInfo.passcode" class="passcode-box">
            <span class="passcode-label">提取码：</span>
            <el-tag type="warning" size="large">{{ shareInfo.passcode }}</el-tag>
            <el-button link type="primary" @click="copyFullShare" style="margin-left: 10px">复制链接+提取码</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="shareResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 转存对话框 -->
    <el-dialog v-model="transferDialogVisible" title="转存到网盘" width="800px">
      <div class="transfer-dialog-content">
        <div v-if="shareContentInfo" class="share-content-info">
          <h4>选择要转存的文件：</h4>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 15px">
            <template #title>
              <span>已加载 {{ shareContentInfo.files?.length || 0 }} 个文件，请勾选需要转存的文件或文件夹</span>
            </template>
          </el-alert>
          
          <!-- 分享文件列表树形结构 -->
          <el-tree
            ref="shareFileTreeRef"
            :data="shareFileTree"
            :props="{ label: 'file_name', children: 'children' }"
            node-key="fid"
            lazy
            show-checkbox
            :check-strictly="false"
            :expand-on-click-node="true"
            :load="loadShareFolderNode"
            @check-change="handleShareFileCheckChange"
          >
            <template #default="{ data }">
              <span class="tree-node">
                <el-icon v-if="data.file_type === 0" style="color: rgb(var(--quark-primary-rgb)); margin-right: 5px"><Folder /></el-icon>
                <el-icon v-else style="color: rgb(var(--quark-accent-rgb)); margin-right: 5px"><Document /></el-icon>
                <span>{{ data.file_name }}</span>
                <span class="file-size" v-if="data.file_type !== 0 && data.size">{{ formatSize(data.size) }}</span>
                <el-tag v-if="data.file_type === 0 && !data.isLeaf" size="small" type="info" style="margin-left: 8px">可展开</el-tag>
                <el-tag v-else-if="data.file_type === 0 && data.children" size="small" style="margin-left: 8px">{{ data.children.length }} 个子项</el-tag>
              </span>
            </template>
          </el-tree>
        </div>
        <el-divider />
        <h4>选择保存位置：</h4>
        <p class="upload-location-hint">
          未选择时默认保存到根目录的“来自：分享”文件夹，不存在则自动创建。
        </p>
        <el-tree
          :data="folderTree"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          highlight-current
          :expand-on-click-node="true"
          :default-expanded-keys="['0']"
          @node-click="handleTransferTargetSelect"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-icon style="margin-right: 5px; color: rgb(var(--quark-primary-rgb))"><Folder /></el-icon>
              <span>{{ data.name }}</span>
              <el-tag v-if="data.id === currentFolderId" size="small" type="warning" style="margin-left: 8px">当前目录</el-tag>
              <el-tag v-if="data.name === '来自：分享'" size="small" type="success" style="margin-left: 8px">默认</el-tag>
            </span>
          </template>
        </el-tree>
      </div>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmTransfer" :loading="transferConfirmLoading" :disabled="selectedShareFileIds.length === 0">
          确定转存 ({{ selectedShareFileIds.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- 下载分享对话框 -->
    <el-dialog v-model="downloadShareDialogVisible" title="下载分享内容" width="800px">
      <div class="download-share-content">
        <div v-if="shareContentInfo" class="share-content-info">
          <h4>选择要下载的文件：</h4>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 15px">
            <template #title>
              <span>已加载 {{ shareContentInfo.files?.length || 0 }} 个文件，请勾选需要下载的文件或文件夹</span>
            </template>
          </el-alert>
          
          <!-- 分享文件列表树形结构 -->
          <el-tree
            ref="downloadShareFileTreeRef"
            :data="shareFileTree"
            :props="{ label: 'file_name', children: 'children' }"
            node-key="fid"
            lazy
            show-checkbox
            :check-strictly="false"
            :expand-on-click-node="true"
            :load="loadShareFolderNode"
            @check-change="handleDownloadShareFileCheckChange"
          >
            <template #default="{ data }">
              <span class="tree-node">
                <el-icon v-if="data.file_type === 0" style="color: rgb(var(--quark-primary-rgb)); margin-right: 5px"><Folder /></el-icon>
                <el-icon v-else style="color: rgb(var(--quark-accent-rgb)); margin-right: 5px"><Document /></el-icon>
                <span>{{ data.file_name }}</span>
                <span class="file-size" v-if="data.file_type !== 0 && data.size">{{ formatSize(data.size) }}</span>
                <el-tag v-if="data.file_type === 0 && !data.isLeaf" size="small" type="info" style="margin-left: 8px">可展开</el-tag>
              </span>
            </template>
          </el-tree>
        </div>
        <el-divider />
        <h4>选择转存位置：</h4>
        <el-tree
          :data="folderTree"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          highlight-current
          :expand-on-click-node="true"
          :default-expanded-keys="['0']"
          @node-click="handleDownloadTargetSelect"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-icon style="margin-right: 5px; color: rgb(var(--quark-primary-rgb))"><Folder /></el-icon>
              <span>{{ data.name }}</span>
              <el-tag v-if="data.name === '来自：分享'" size="small" type="success" style="margin-left: 8px">默认</el-tag>
            </span>
          </template>
        </el-tree>
        <el-alert type="warning" :closable="false" style="margin-top: 15px">
          <template #title>
            文件将转存到选中位置后下载，需要开启 Motrix RPC 服务
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="downloadShareDialogVisible = false">取消</el-button>
        <el-button type="success" @click="confirmDownloadShare('keep')" :loading="downloadShareConfirmLoading" :disabled="selectedDownloadShareFileIds.length === 0">
          保存下载 ({{ selectedDownloadShareFileIds.length }})
        </el-button>
        <el-button type="primary" @click="confirmDownloadShare('clean')" :loading="downloadShareConfirmLoading" :disabled="selectedDownloadShareFileIds.length === 0">
          无痕下载 ({{ selectedDownloadShareFileIds.length }})
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 上传对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传文件" width="600px" @close="handleUploadDialogClose">
      <div class="upload-content">
        <!-- 拖拽上传区域 -->
        <div
          class="upload-drop-zone"
          :class="{ 'is-dragging': isDragging }"
          @drop.prevent="handleDrop"
          @dragover.prevent="handleDragOver"
          @dragleave.prevent="handleDragLeave"
        >
          <el-icon class="upload-icon" :size="48"><Upload /></el-icon>
          <p class="upload-text">拖拽文件/文件夹到此处上传</p>
          <p class="upload-hint">或使用下方按钮选择，支持 Ctrl+V 粘贴</p>
          <div class="upload-buttons">
            <el-button type="primary" @click="triggerFileSelect">
              <el-icon style="margin-right: 5px"><Document /></el-icon>
              选择文件
            </el-button>
            <el-button type="success" @click="triggerFolderSelect">
              <el-icon style="margin-right: 5px"><Folder /></el-icon>
              选择文件夹
            </el-button>
          </div>
          <input
            ref="fileInputRef"
            type="file"
            multiple
            style="display: none"
            @change="handleFileSelect"
          />
          <input
            ref="folderInputRef"
            type="file"
            webkitdirectory
            directory
            multiple
            style="display: none"
            @change="handleFolderSelect"
          />
        </div>
        
        <!-- 已选择的文件列表 -->
        <div v-if="uploadFiles.length > 0" class="upload-file-list">
          <div class="upload-file-header">
            <span>已选择 {{ uploadFiles.length }} 个文件（共 {{ formatSize(totalUploadSize) }}）</span>
            <el-button link type="danger" size="small" @click="clearUploadFiles">清空</el-button>
          </div>
          <div class="upload-file-items">
            <div v-for="(item, index) in uploadSelectionItems" :key="`${item.path}-${index}`" class="upload-file-item">
              <el-icon v-if="item.isFolder" style="color: rgb(var(--quark-primary-rgb)); margin-right: 8px"><Folder /></el-icon>
              <el-icon v-else style="color: rgb(var(--quark-accent-rgb)); margin-right: 8px"><Document /></el-icon>
              <span class="file-name" :title="item.path">
                {{ item.path }}
              </span>
              <span class="file-size">{{ formatSize(item.size) }}</span>
              <el-button
                v-if="!item.isFolder"
                link
                type="danger"
                size="small"
                @click="removeUploadFileByPath(item.sourcePath)"
              >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        
        <el-divider />
        
        <h4>上传位置：</h4>
        <p class="upload-location-hint">
          未选择时默认上传到根目录的“夸克上传文件”文件夹，不存在则自动创建。
        </p>
        <el-tree
          :data="folderTree"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          highlight-current
          :expand-on-click-node="true"
          :default-expanded-keys="['0']"
          @node-click="(data: any) => uploadTargetFolderId = data.id"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-icon style="margin-right: 5px; color: rgb(var(--quark-primary-rgb))"><Folder /></el-icon>
              <span>{{ data.name }}</span>
              <el-tag v-if="data.id === currentFolderId" size="small" type="warning" style="margin-left: 8px">当前目录</el-tag>
              <el-tag v-if="data.name === '夸克上传文件'" size="small" type="success" style="margin-left: 8px">默认</el-tag>
            </span>
          </template>
        </el-tree>
        
        <div v-if="uploadLoading" style="margin-top: 15px">
          <el-progress :percentage="uploadProgress" :stroke-width="8" />
          <p style="text-align: center; margin-top: 10px; color: #909399">正在上传，请稍候...</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="uploadDialogVisible = false" :disabled="uploadLoading">取消</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="uploadLoading" :disabled="uploadFiles.length === 0">
          开始上传 ({{ uploadFiles.length }})
        </el-button>
      </template>
    </el-dialog>

    <div v-if="uploadTasks.length > 0" class="upload-task-panel">
      <div class="upload-task-header">
        <div>
          <div class="upload-task-title">上传任务</div>
          <div class="upload-task-subtitle">
            {{ uploadingTaskCount > 0 ? `进行中 ${uploadingTaskCount}` : `已完成 ${completedTaskCount}` }}
          </div>
        </div>
        <el-button link type="primary" @click="clearFinishedUploadTasks">
          清理完成项
        </el-button>
      </div>
      <div class="upload-task-list">
        <div v-for="task in visibleUploadTasks" :key="task.id" class="upload-task-item">
          <div class="upload-task-name-row">
            <span class="upload-task-name" :title="task.path">{{ task.path }}</span>
            <span class="upload-task-status" :class="`is-${task.status}`">{{ getUploadTaskStatusText(task.status) }}</span>
          </div>
          <el-progress
            :percentage="task.progress"
            :status="task.status === 'error' ? 'exception' : task.status === 'success' ? 'success' : undefined"
            :stroke-width="6"
          />
          <div class="upload-task-meta">
            <span>{{ formatSize(task.size) }}</span>
            <span>{{ task.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Upload, FolderAdd, Folder, Document, Refresh, SwitchButton,
  Search, More, PieChart, VideoPlay, Headset, Picture, DocumentCopy,
  User, Link, Download, CaretTop, CaretBottom, Close
} from '@element-plus/icons-vue'
import { filesAPI } from '@/api/modules/quark'
import { useQuarkUserStore } from '@/stores'

const router = useRouter()
const userStore = useQuarkUserStore()

const loading = ref(false)
const currentFolderId = ref('0')
const searchKeyword = ref('')
const selectedFiles = ref<any[]>([])
const storageInfo = ref<{ total: number; used: number }>({ total: 0, used: 0 })
const storageDialogVisible = ref(false)
const moveDialogVisible = ref(false)
const moveTargetId = ref('')
const folderTree = ref<any[]>([])
const moveFileIds = ref<string[]>([])
const userInfo = ref<any>(null)

// 分享相关
const shareDialogVisible = ref(false)
const shareResultVisible = ref(false)
const shareInfo = ref<any>(null)
const shareFileIds = ref<string[]>([])
const shareExpireDays = ref(0)
const sharePassword = ref('')
const shareLoading = ref(false)

// 移动相关
const moveFileNames = ref<string[]>([])

// 分享链接转存/下载相关
const shareLinkInput = ref('')
const shareLinkPasscode = ref('')
const transferLoading = ref(false)
const downloadShareLoading = ref(false)
const transferDialogVisible = ref(false)
const downloadShareDialogVisible = ref(false)
const shareContentInfo = ref<any>(null)
const shareFileTree = ref<any[]>([])
const selectedShareFileIds = ref<string[]>([])
const shareFileTreeRef = ref<any>(null)
const transferTargetFolderId = ref('')
const transferConfirmLoading = ref(false)
const downloadShareConfirmLoading = ref(false)
const downloadShareFileTreeRef = ref<any>(null)
const selectedDownloadShareFileIds = ref<string[]>([])
const downloadTargetFolderId = ref('')

const pathList = ref([
  { id: '0', name: '根目录' }
])

const fileList = ref<any[]>([])

const findPreferredRootFolderId = (folderName: string): string => {
  const roots = folderTree.value?.[0]?.children || []
  const directMatch = roots.find((node: any) => node.name === folderName)
  if (directMatch) return directMatch.id

  const findRecursive = (nodes: any[]): string => {
    for (const node of nodes) {
      if (node.name === folderName) return node.id
      if (node.children?.length) {
        const found = findRecursive(node.children)
        if (found) return found
      }
    }
    return ''
  }

  return findRecursive(folderTree.value || [])
}

// 排序状态
const nameSortOrder = ref<'asc' | 'desc' | ''>('')
const timeSortOrder = ref<'asc' | 'desc' | ''>('')

const canGoBack = computed(() => pathList.value.length > 1)

const storagePercentage = computed(() => {
  if (!storageInfo.value || storageInfo.value.total === 0) return 0
  return Math.round((storageInfo.value.used / storageInfo.value.total) * 100)
})

// 排序后的文件列表
const sortedFileList = computed(() => {
  const list = [...fileList.value]
  
  if (nameSortOrder.value) {
    list.sort((a, b) => {
      // 文件夹始终在前
      if (a.file_type === 0 && b.file_type !== 0) return -1
      if (a.file_type !== 0 && b.file_type === 0) return 1
      
      const nameA = a.file_name.toLowerCase()
      const nameB = b.file_name.toLowerCase()
      if (nameSortOrder.value === 'asc') {
        return nameA.localeCompare(nameB, 'zh-CN')
      } else {
        return nameB.localeCompare(nameA, 'zh-CN')
      }
    })
  } else if (timeSortOrder.value) {
    list.sort((a, b) => {
      // 文件夹始终在前
      if (a.file_type === 0 && b.file_type !== 0) return -1
      if (a.file_type !== 0 && b.file_type === 0) return 1
      
      const timeA = new Date(a.updated_at || 0).getTime()
      const timeB = new Date(b.updated_at || 0).getTime()
      if (timeSortOrder.value === 'asc') {
        return timeA - timeB
      } else {
        return timeB - timeA
      }
    })
  }
  
  return list
})

// 排序方法
const toggleNameSort = (order: 'asc' | 'desc') => {
  if (nameSortOrder.value === order) {
    nameSortOrder.value = ''
  } else {
    nameSortOrder.value = order
    timeSortOrder.value = '' // 清除另一个排序
  }
}

const toggleTimeSort = (order: 'asc' | 'desc') => {
  if (timeSortOrder.value === order) {
    timeSortOrder.value = ''
  } else {
    timeSortOrder.value = order
    nameSortOrder.value = '' // 清除另一个排序
  }
}

// 加载用户信息
const loadUserInfo = async () => {
  try {
    const response = await filesAPI.getUserInfo()
    if (response.success && response.data) {
      userInfo.value = response.data
      // 同时更新存储信息
      if (response.data.total_capacity !== undefined) {
        storageInfo.value = {
          total: response.data.total_capacity || 0,
          used: response.data.use_capacity || 0
        }
      }
    }
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

// 加载存储信息
const loadStorageInfo = async () => {
  try {
    const response = await filesAPI.getStorageInfo()
    if (response.success && response.data) {
      storageInfo.value = {
        total: response.data.total || 0,
        used: response.data.used || 0
      }
    }
  } catch (error) {
    console.error('获取存储信息失败:', error)
  }
}

// 加载文件列表
const loadFiles = async () => {
  loading.value = true
  try {
    const response = await filesAPI.listFiles(currentFolderId.value)
    console.log('前端当前文件夹的fid:', currentFolderId.value)
    console.log('后端返回的文件列表:', response.data?.data?.list || [])
    if (response.success && response.data) {
      fileList.value = response.data.data?.list || []
    } else {
      ElMessage.error(response.message || '获取文件列表失败')
    }
  } catch (error: any) {
    console.error('获取文件列表失败:', error)
    ElMessage.error(error.response?.data?.detail || '获取文件列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索文件
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    loadFiles()
    return
  }
  
  loading.value = true
  try {
    const response = await filesAPI.searchFiles(searchKeyword.value)
    if (response.success && response.data) {
      fileList.value = response.data.data?.list || []
      // 重置路径为搜索结果
      pathList.value = [{ id: '0', name: `搜索: ${searchKeyword.value}` }]
    }
  } catch (error: any) {
    ElMessage.error('搜索失败')
  } finally {
    loading.value = false
  }
}

// 返回上级
const goBack = () => {
  if (pathList.value.length > 1) {
    pathList.value.pop()
    const parent = pathList.value[pathList.value.length - 1]
    currentFolderId.value = parent.id
    searchKeyword.value = ''
    loadFiles()
  }
}

// 导航到指定路径
const navigateTo = (index: number) => {
  if (index < pathList.value.length - 1) {
    pathList.value = pathList.value.slice(0, index + 1)
    const target = pathList.value[index]
    currentFolderId.value = target.id
    searchKeyword.value = ''
    loadFiles()
  }
}

// 双击行
const handleRowClick = (row: any) => {
  if (row.file_type === 0) { // 文件夹 (file_type=0 表示文件夹)
    currentFolderId.value = row.fid
    pathList.value.push({ id: row.fid, name: row.file_name })
    searchKeyword.value = ''
    loadFiles()
  }
}

// 选择变化
const handleSelectionChange = (selection: any[]) => {
  selectedFiles.value = selection
}

// 清除选择
const clearSelection = () => {
  selectedFiles.value = []
}

// 下拉菜单命令
const handleCommand = (command: string) => {
  switch (command) {
    case 'storage':
      storageDialogVisible.value = true
      break
    case 'logout':
      handleLogout()
      break
  }
}

// 格式化文件大小
const formatSize = (bytes: number): string => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化文件夹大小
const formatFolderSize = (dirSize: number): string => {
  if (!dirSize) return '-'
  return formatSize(dirSize)
}

// 格式化日期时间
const formatDateTime = (dateStr: string): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

// 获取文件图标
const getFileIcon = (row: any) => {
  if (row.file_type === 0) return Folder  // file_type=0 表示文件夹
  
  const ext = getFileExtension(row.file_name)
  const iconMap: Record<string, any> = {
    // 视频
    mp4: VideoPlay, avi: VideoPlay, mkv: VideoPlay, mov: VideoPlay, wmv: VideoPlay,
    // 音频
    mp3: Headset, wav: Headset, flac: Headset, aac: Headset,
    // 图片
    jpg: Picture, jpeg: Picture, png: Picture, gif: Picture, bmp: Picture, webp: Picture,
    // 文档
    pdf: DocumentCopy, doc: DocumentCopy, docx: DocumentCopy, xls: DocumentCopy, xlsx: DocumentCopy,
    ppt: DocumentCopy, pptx: DocumentCopy, txt: DocumentCopy,
  }
  
  return iconMap[ext] || Document
}

// 获取文件图标颜色
const getFileIconColor = (row: any) => {
  if (row.file_type === 0) return 'rgb(var(--quark-primary-rgb))'
  
  const ext = getFileExtension(row.file_name)
  const colorMap: Record<string, string> = {
    mp4: 'rgb(var(--quark-accent-rgb))', avi: 'rgb(var(--quark-accent-rgb))', mkv: 'rgb(var(--quark-accent-rgb))', mov: 'rgb(var(--quark-accent-rgb))',
    mp3: '#e6a23c', wav: '#e6a23c', flac: '#e6a23c',
    jpg: '#f56c6c', jpeg: '#f56c6c', png: '#f56c6c', gif: '#f56c6c',
    pdf: '#f56c6c', doc: 'rgb(var(--quark-primary-rgb))', docx: 'rgb(var(--quark-primary-rgb))', xls: 'rgb(var(--quark-accent-rgb))', xlsx: 'rgb(var(--quark-accent-rgb))',
    ppt: '#e6a23c', pptx: '#e6a23c', txt: 'rgb(var(--quark-text-subtle-rgb))',
  }
  
  return colorMap[ext] || 'rgb(var(--quark-text-subtle-rgb))'
}

// 获取文件图标类
const getFileIconClass = (row: any) => {
  return row.file_type === 0 ? 'folder-icon' : 'file-icon'  // file_type=0 表示文件夹
}

// 获取文件扩展名
const getFileExtension = (filename: string): string => {
  if (!filename) return ''
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop()!.toLowerCase() : ''
}

// 上传文件
interface UploadFileItem {
  file: File
  name: string
  size: number
  relativePath?: string // 相对路径，用于文件夹上传
}

interface UploadTaskItem {
  id: string
  name: string
  path: string
  size: number
  progress: number
  status: 'waiting' | 'uploading' | 'success' | 'error'
  message: string
}

interface PendingUploadQueueItem {
  taskId: string
  item: UploadFileItem
  targetFolderId: string
}

interface UploadSelectionDisplayItem {
  path: string
  size: number
  isFolder: boolean
  sourcePath: string
}

const uploadDialogVisible = ref(false)
const uploadFiles = ref<UploadFileItem[]>([])
const uploadProgress = ref(0)
const uploadLoading = ref(false)
const uploadTargetFolderId = ref('')
const isDragging = ref(false)
const isMainDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)
const uploadTasks = ref<UploadTaskItem[]>([])
const pendingUploadQueue = ref<PendingUploadQueueItem[]>([])
const isProcessingUploadQueue = ref(false)
const shouldRefreshAfterUploads = ref(false)

const visibleUploadTasks = computed(() => uploadTasks.value.slice(-8).reverse())
const uploadingTaskCount = computed(() => uploadTasks.value.filter(task => task.status === 'uploading' || task.status === 'waiting').length)
const completedTaskCount = computed(() => uploadTasks.value.filter(task => task.status === 'success').length)

// 计算总上传大小
const totalUploadSize = computed(() => {
  return uploadFiles.value.reduce((sum, item) => sum + item.size, 0)
})

const uploadSelectionItems = computed<UploadSelectionDisplayItem[]>(() => {
  const collapsedFolders = new Map<string, UploadSelectionDisplayItem>()
  const displayItems: UploadSelectionDisplayItem[] = []

  for (const item of uploadFiles.value) {
    if (item.relativePath && item.relativePath.includes('/')) {
      const topLevelFolder = item.relativePath.split('/')[0]
      const existingFolder = collapsedFolders.get(topLevelFolder)
      if (existingFolder) {
        existingFolder.size += item.size
      } else {
        const folderItem = {
          path: topLevelFolder,
          size: item.size,
          isFolder: true,
          sourcePath: topLevelFolder
        }
        collapsedFolders.set(topLevelFolder, folderItem)
        displayItems.push(folderItem)
      }
      continue
    }

    displayItems.push({
      path: item.relativePath || item.name,
      size: item.size,
      isFolder: false,
      sourcePath: item.relativePath || item.name
    })
  }

  return displayItems
})

const addUploadItems = (items: UploadFileItem[]) => {
  const existingPaths = new Set(uploadFiles.value.map(item => item.relativePath || item.name))
  const newItems: UploadFileItem[] = []

  for (const item of items) {
    const uniquePath = item.relativePath || item.name
    if (!existingPaths.has(uniquePath)) {
      newItems.push(item)
      existingPaths.add(uniquePath)
    }
  }

  uploadFiles.value = [...uploadFiles.value, ...newItems]

  if (newItems.length < items.length) {
    ElMessage.warning(`${items.length - newItems.length} 个重复文件已跳过`)
  }
}

const readFileEntry = (entry: any): Promise<File> => {
  return new Promise((resolve, reject) => {
    entry.file(resolve, reject)
  })
}

const readDirectoryBatch = (reader: any): Promise<any[]> => {
  return new Promise((resolve, reject) => {
    reader.readEntries(resolve, reject)
  })
}

const flattenEntryFiles = async (entry: any, parentPath = ''): Promise<UploadFileItem[]> => {
  if (!entry) return []

  if (entry.isFile) {
    const file = await readFileEntry(entry)
    const relativePath = parentPath ? `${parentPath}/${file.name}` : file.name
    return [{
      file,
      name: file.name,
      size: file.size,
      relativePath
    }]
  }

  if (entry.isDirectory) {
    const reader = entry.createReader()
    const directoryPath = parentPath ? `${parentPath}/${entry.name}` : entry.name
    const allChildren: any[] = []

    while (true) {
      const batch = await readDirectoryBatch(reader)
      if (!batch.length) break
      allChildren.push(...batch)
    }

    const files: UploadFileItem[] = []
    for (const child of allChildren) {
      files.push(...await flattenEntryFiles(child, directoryPath))
    }
    return files
  }

  return []
}

const extractUploadItemsFromDataTransfer = async (dataTransfer: DataTransfer): Promise<UploadFileItem[]> => {
  const items = Array.from(dataTransfer.items || [])
  const entries = items
    .map(item => (item as any).webkitGetAsEntry?.())
    .filter(Boolean)

  if (entries.length > 0) {
    const files: UploadFileItem[] = []
    for (const entry of entries) {
      files.push(...await flattenEntryFiles(entry))
    }
    return files
  }

  return Array.from(dataTransfer.files || []).map(file => ({
    file,
    name: file.name,
    size: file.size,
    relativePath: (file as any).webkitRelativePath || undefined
  }))
}

const createUploadTaskId = (item: UploadFileItem) => `${item.relativePath || item.name}-${item.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const initializeUploadTasks = (items: UploadFileItem[]) => {
  const newTasks = items.map(item => ({
    id: createUploadTaskId(item),
    name: item.name,
    path: item.relativePath || item.name,
    size: item.size,
    progress: 0,
    status: 'waiting' as const,
    message: '等待上传'
  }))

  uploadTasks.value = [...uploadTasks.value, ...newTasks]
  return newTasks
}

const updateUploadTask = (taskId: string, patch: Partial<UploadTaskItem>) => {
  const task = uploadTasks.value.find(item => item.id === taskId)
  if (!task) return
  Object.assign(task, patch)
}

const clearFinishedUploadTasks = () => {
  uploadTasks.value = uploadTasks.value.filter(task => task.status !== 'success')
}

const getUploadTaskStatusText = (status: UploadTaskItem['status']) => {
  switch (status) {
    case 'waiting':
      return '等待中'
    case 'uploading':
      return '上传中'
    case 'success':
      return '已完成'
    case 'error':
      return '失败'
    default:
      return ''
  }
}

const uploadSingleItem = async (
  item: UploadFileItem,
  targetFolderId: string,
  taskId: string
) => {
  updateUploadTask(taskId, {
    status: 'uploading',
    progress: 0,
    message: '开始上传'
  })

  const response = await filesAPI.uploadFile(
    item.file,
    targetFolderId,
    (progress) => {
      updateUploadTask(taskId, {
        status: 'uploading',
        progress,
        message: `上传中 ${progress}%`
      })
    },
    item.relativePath
  )

  if (response.success) {
    updateUploadTask(taskId, {
      status: 'success',
      progress: 100,
      message: '上传完成'
    })
    return true
  }

  updateUploadTask(taskId, {
    status: 'error',
    progress: 100,
    message: response.message || '上传失败'
  })
  return false
}

const enqueueUploadItems = (items: UploadFileItem[], targetFolderId: string) => {
  const tasks = initializeUploadTasks(items)
  pendingUploadQueue.value.push(
    ...items.map((item, index) => ({
      taskId: tasks[index].id,
      item,
      targetFolderId
    }))
  )
  void processUploadQueue()
  return tasks
}

const processUploadQueue = async () => {
  if (isProcessingUploadQueue.value) return
  isProcessingUploadQueue.value = true

  try {
    while (pendingUploadQueue.value.length > 0) {
      const current = pendingUploadQueue.value.shift()
      if (!current) continue

      try {
        const success = await uploadSingleItem(current.item, current.targetFolderId, current.taskId)
        if (success) {
          shouldRefreshAfterUploads.value = true
        }
      } catch (error: any) {
        updateUploadTask(current.taskId, {
          status: 'error',
          progress: 100,
          message: error?.message || '上传失败'
        })
      }
    }
  } finally {
    isProcessingUploadQueue.value = false
    if (shouldRefreshAfterUploads.value) {
      shouldRefreshAfterUploads.value = false
      refreshAll()
    }
  }
}

// 点击上传按钮
const handleUpload = async () => {
  // 先加载文件夹树
  await loadFolderTree()
  uploadTargetFolderId.value = ''
  uploadDialogVisible.value = true
}

// 触发文件选择
const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

// 触发文件夹选择
const triggerFolderSelect = () => {
  folderInputRef.value?.click()
}

// 文件选择变化
const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    addFiles(Array.from(target.files))
  }
}

// 文件夹选择变化
const handleFolderSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    addFilesWithPaths(Array.from(target.files))
  }
}

// 添加文件到列表（普通文件）
const addFiles = (files: File[]) => {
  addUploadItems(files.map(file => ({
    file,
    name: file.name,
    size: file.size,
    relativePath: undefined
  })))
}

// 添加文件到列表（带路径，用于文件夹）
const addFilesWithPaths = (files: File[]) => {
  const uploadItems = files.map(file => ({
    file,
    name: file.name,
    size: file.size,
    relativePath: (file as any).webkitRelativePath || file.name
  }))

  addUploadItems(uploadItems)

  if (uploadItems.length > 0) {
    ElMessage.success(`已添加 ${uploadItems.length} 个文件`)
  }
}

// 移除单个文件
const removeUploadFile = (index: number) => {
  uploadFiles.value.splice(index, 1)
}

const removeUploadFileByPath = (path: string) => {
  const index = uploadFiles.value.findIndex(item => (item.relativePath || item.name) === path)
  if (index >= 0) {
    removeUploadFile(index)
  }
}

// 清空文件列表
const clearUploadFiles = () => {
  uploadFiles.value = []
}

// 拖拽进入（对话框区域）
const handleDragOver = (_e: DragEvent) => {
  isDragging.value = true
}

// 拖拽离开（对话框区域）
const handleDragLeave = (_e: DragEvent) => {
  isDragging.value = false
}

// 拖拽放下（对话框区域）
const handleDrop = async (e: DragEvent) => {
  isDragging.value = false
  const dataTransfer = e.dataTransfer
  if (dataTransfer) {
    const items = await extractUploadItemsFromDataTransfer(dataTransfer)
    addUploadItems(items)
    if (items.length > 0) {
      ElMessage.success(`已添加 ${items.length} 个文件`)
    }
  }
}

// 主内容区拖拽进入
const handleMainDragOver = (e: DragEvent) => {
  // 检查是否是文件拖拽
  if (e.dataTransfer?.types.includes('Files')) {
    isMainDragging.value = true
  }
}

// 主内容区拖拽离开
const handleMainDragLeave = (e: DragEvent) => {
  // 检查是否真正离开了主内容区
  const relatedTarget = e.relatedTarget as Node
  const currentTarget = e.currentTarget as Node
  if (!currentTarget.contains(relatedTarget)) {
    isMainDragging.value = false
  }
}

// 主内容区拖拽放下 - 直接上传
const handleMainDrop = async (e: DragEvent) => {
  isMainDragging.value = false
  const dataTransfer = e.dataTransfer
  if (dataTransfer) {
    const items = await extractUploadItemsFromDataTransfer(dataTransfer)
    await uploadFilesDirectly(items)
  }
}

// 直接上传文件到当前文件夹
const uploadFilesDirectly = async (items: UploadFileItem[]) => {
  if (items.length === 0) return
  
  // 检查是否有文件夹
  const hasFolder = items.some(item => item.relativePath && item.relativePath.includes('/'))
  
  if (hasFolder) {
    uploadFilesWithFolderStructure(items, currentFolderId.value)
  } else {
    ElMessage.info(`开始上传 ${items.length} 个文件到当前文件夹...`)
    enqueueUploadItems(items, currentFolderId.value)
    ElMessage.success(`已提交 ${items.length} 个上传任务`)
  }
}

// 上传带文件夹结构的文件，任务列表按文件维度展示
const uploadFilesWithFolderStructure = (items: UploadFileItem[], targetFolderId: string) => {
  const totalFiles = items.length
  let createdFolders = 0

  const folderSet = new Set<string>()
  for (const item of items) {
    if (!item.relativePath || !item.relativePath.includes('/')) continue
    const parts = item.relativePath.split('/')
    for (let index = 1; index < parts.length; index++) {
      folderSet.add(parts.slice(0, index).join('/'))
    }
  }
  createdFolders = folderSet.size

  enqueueUploadItems(items, targetFolderId)
  ElMessage.success(`已提交 ${totalFiles} 个文件上传任务，将重建 ${createdFolders} 个文件夹`)
}

// 粘贴文件
const handlePaste = async (e: ClipboardEvent) => {
  const items = e.clipboardData?.items
  if (!items) return
  
  const files: File[] = []
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.kind === 'file') {
      const file = item.getAsFile()
      if (file) {
        files.push(file)
      }
    }
  }
  
  if (files.length > 0) {
    if (uploadDialogVisible.value) {
      // 对话框打开时，添加到列表
      addFiles(files)
      ElMessage.success(`已粘贴 ${files.length} 个文件`)
    } else {
      // 对话框关闭时，直接上传到当前文件夹
      const uploadItems: UploadFileItem[] = files.map(f => ({
        file: f,
        name: f.name,
        size: f.size,
        relativePath: undefined
      }))
      await uploadFilesDirectly(uploadItems)
    }
  }
}

// 关闭上传对话框
const handleUploadDialogClose = () => {
  if (!uploadLoading.value) {
    uploadFiles.value = []
    uploadProgress.value = 0
    if (fileInputRef.value) fileInputRef.value.value = ''
    if (folderInputRef.value) folderInputRef.value.value = ''
  }
}

// 确认上传
const confirmUpload = async () => {
  if (uploadFiles.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  
  uploadLoading.value = true
  uploadProgress.value = 0
  
  const targetId = uploadTargetFolderId.value || ''
  const filesToUpload = [...uploadFiles.value]
  
  // 检查是否有文件夹结构
  const hasFolder = filesToUpload.some(item => item.relativePath && item.relativePath.includes('/'))
  
  if (hasFolder) {
    uploadFilesWithFolderStructure(filesToUpload, targetId)
  } else {
    enqueueUploadItems(filesToUpload, targetId)
    ElMessage.success(`已提交 ${filesToUpload.length} 个上传任务`)
  }
  
  uploadLoading.value = false
  uploadDialogVisible.value = false
  uploadFiles.value = []
  uploadProgress.value = 0
  if (fileInputRef.value) fileInputRef.value.value = ''
  if (folderInputRef.value) folderInputRef.value.value = ''
  refreshAll()
}

// 新建文件夹
const handleCreateFolder = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '文件夹名称不能为空'
    })
    
    const response = await filesAPI.createFolder(value, currentFolderId.value)
    if (response.success) {
      ElMessage.success('创建成功')
      refreshAll()
    } else {
      ElMessage.error(response.message || '创建失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 下载文件
const handleDownload = async (row: any) => {
  try {
    // file_type: 0=文件夹, 1=文件
    if (row.file_type === 0) {
      // 文件夹下载
      const response = await filesAPI.downloadFolder(row.fid, row.file_name)
      if (response.success) {
        ElMessage.success(response.message)
      } else {
        ElMessage.error(response.message || '文件夹下载失败')
      }
    } else {
      // 文件下载
      const response = await filesAPI.getDownloadUrl(row.fid, row.file_name)
      if (response.success) {
        if (response.data?.download_url) {
          // RPC 未开启，浏览器直接下载
          window.open(response.data.download_url, '_blank')
        } else if (response.message) {
          // RPC 已开启，已发送到 Motrix
          ElMessage.success(response.message)
        }
      } else {
        ElMessage.error(response.message || '获取下载链接失败')
      }
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '下载失败')
  }
}

// 重命名
const handleRename = async (row: any) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: row.file_name,
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空'
    })
    
    const response = await filesAPI.renameFile(row.fid, value)
    if (response.success) {
      ElMessage.success('重命名成功')
      refreshAll()
    } else {
      ElMessage.error(response.message || '重命名失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 删除
const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定要删除 "${row.file_name}" 吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const response = await filesAPI.deleteFiles([row.fid])
    if (response.success) {
      ElMessage.success('删除成功')
      refreshAll()
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 批量下载
const handleBatchDownload = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请选择要下载的文件或文件夹')
    return
  }
  
  // 分离文件夹和文件
  const folders = selectedFiles.value.filter(f => f.file_type === 0)  // 文件夹
  const files = selectedFiles.value.filter(f => f.file_type !== 0)    // 文件
  
  let rpcCount = 0
  let browserCount = 0
  let folderCount = 0
  
  // 下载文件夹
  for (const folder of folders) {
    try {
      const response = await filesAPI.downloadFolder(folder.fid, folder.file_name)
      if (response.success) {
        folderCount++
        ElMessage.success(response.message || `文件夹 ${folder.file_name} 已开始下载`)
      } else {
        ElMessage.error(response.message || `文件夹 ${folder.file_name} 下载失败`)
      }
    } catch (error: any) {
      console.error(`下载文件夹 ${folder.file_name} 失败:`, error)
      ElMessage.error(error.response?.data?.detail || `文件夹 ${folder.file_name} 下载失败`)
    }
  }
  
  // 下载文件
  for (const file of files) {
    try {
      const response = await filesAPI.getDownloadUrl(file.fid, file.file_name)
      if (response.success) {
        if (response.data?.download_url) {
          // RPC 未开启，浏览器下载
          window.open(response.data.download_url, '_blank')
          browserCount++
        } else {
          // RPC 已开启，已发送到 Motrix
          rpcCount++
        }
      }
    } catch (error) {
      console.error(`下载 ${file.file_name} 失败:`, error)
    }
  }
  
  // 显示结果
  const messages: string[] = []
  if (folderCount > 0) messages.push(`${folderCount} 个文件夹`)
  if (rpcCount > 0) messages.push(`${rpcCount} 个文件到 Motrix`)
  if (browserCount > 0) messages.push(`${browserCount} 个文件在浏览器下载`)
  
  if (messages.length > 0) {
    ElMessage.success(`已发送下载任务：${messages.join('，')}`)
  }
  
  clearSelection()
}

// 移动单个文件
const handleMove = async (row: any) => {
  moveFileIds.value = [row.fid]
  moveFileNames.value = [row.file_name]
  await loadFolderTree()
  moveTargetId.value = ''
  moveDialogVisible.value = true
}

// 批量移动
const handleBatchMove = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请选择要移动的文件')
    return
  }
  moveFileIds.value = selectedFiles.value.map(f => f.fid)
  moveFileNames.value = selectedFiles.value.map(f => f.file_name)
  await loadFolderTree()
  moveTargetId.value = ''
  moveDialogVisible.value = true
}

// 加载文件夹树
const loadFolderTree = async () => {
  try {
    const response = await filesAPI.getFolderTree('0', 3)
    if (response.success && response.data) {
      // 后端直接返回树形数组
      if (Array.isArray(response.data)) {
        folderTree.value = response.data
      } else {
        folderTree.value = [{ id: '0', name: '根目录', children: [] }]
      }
    } else {
      folderTree.value = [{ id: '0', name: '根目录', children: [] }]
    }
  } catch (error) {
    console.error('获取文件夹树失败:', error)
    folderTree.value = [{ id: '0', name: '根目录', children: [] }]
  }
}

// 选择移动目标
const handleMoveTargetSelect = (data: any) => {
  moveTargetId.value = data.id
}

// 确认移动
const confirmMove = async () => {
  if (!moveTargetId.value) return
  
  try {
    const response = await filesAPI.moveFiles(moveFileIds.value, moveTargetId.value)
    if (response.success) {
      ElMessage.success('移动成功')
      moveDialogVisible.value = false
      clearSelection()
      refreshAll()
    } else {
      ElMessage.error(response.message || '移动失败')
    }
  } catch (error) {
    ElMessage.error('移动失败')
  }
}

// 分享单个文件
const handleShare = async (row: any) => {
  shareFileIds.value = [row.fid]
  shareExpireDays.value = 0
  sharePassword.value = ''
  await createShare()
}

// 批量分享
const handleBatchShare = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请选择要分享的文件')
    return
  }
  shareFileIds.value = selectedFiles.value.map(f => f.fid)
  shareExpireDays.value = 0
  sharePassword.value = ''
  await createShare()
}

// 创建分享
const createShare = async () => {
  shareLoading.value = true
  try {
    const response = await filesAPI.createShare(
      shareFileIds.value,
      '',
      shareExpireDays.value,
      sharePassword.value || undefined
    )
    console.log('分享响应:', response)
    if (response.success && response.data) {
      shareInfo.value = response.data
      console.log('shareInfo:', shareInfo.value)
      
      // 关闭创建分享对话框
      shareDialogVisible.value = false
      
      // 自动复制链接
      const copied = await copyShareLink()
      
      // 显示分享成功对话框
      shareResultVisible.value = true
      
      if (copied) {
        ElMessage.success('分享链接已创建并复制到剪贴板')
      } else {
        ElMessage.success('分享链接已创建')
      }
    } else {
      ElMessage.error(response.message || '创建分享失败')
    }
  } catch (error: any) {
    console.error('创建分享失败:', error)
    ElMessage.error(error.message || '创建分享失败')
  } finally {
    shareLoading.value = false
  }
}

// 复制分享链接
const copyShareLink = async () => {
  if (shareInfo.value?.share_url) {
    try {
      await navigator.clipboard.writeText(shareInfo.value.share_url)
      return true
    } catch {
      return false
    }
  }
  return false
}

// 手动点击复制按钮
const handleCopyLink = async () => {
  const copied = await copyShareLink()
  if (copied) {
    ElMessage.success('链接已复制到剪贴板')
  } else {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 复制链接+提取码
const copyFullShare = async () => {
  if (shareInfo.value?.share_url) {
    const text = shareInfo.value.passcode 
      ? `${shareInfo.value.share_url} 提取码：${shareInfo.value.passcode}`
      : shareInfo.value.share_url
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success('链接和提取码已复制到剪贴板')
    } catch {
      ElMessage.error('复制失败，请手动复制')
    }
  }
}

// 刷新所有数据
const refreshAll = () => {
  loadFiles()
  loadStorageInfo()
  loadUserInfo()
}

// 批量删除
const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedFiles.value.length} 项吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const fileIds = selectedFiles.value.map(f => f.fid)
    const response = await filesAPI.deleteFiles(fileIds)
    if (response.success) {
      ElMessage.success('删除成功')
      clearSelection()
      refreshAll()
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 批量重命名（选中单个时可用）
const handleBatchRename = async () => {
  if (selectedFiles.value.length !== 1) {
    ElMessage.warning('请选择一个文件进行重命名')
    return
  }
  
  const file = selectedFiles.value[0]
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: file.file_name,
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空'
    })
    
    const response = await filesAPI.renameFile(file.fid, value)
    if (response.success) {
      ElMessage.success('重命名成功')
      clearSelection()
      refreshAll()
    } else {
      ElMessage.error(response.message || '重命名失败')
    }
  } catch (error) {
    // 用户取消
  }
}

// 解析分享链接
const parseShareLink = () => {
  if (!shareLinkInput.value.trim()) {
    ElMessage.warning('请输入分享链接')
    return null
  }
  
  // 从链接中提取分享ID
  const match = shareLinkInput.value.match(/pan\.quark\.cn\/s\/([a-zA-Z0-9]+)/)
  if (!match) {
    ElMessage.error('无效的分享链接格式')
    return null
  }
  
  return match[1]
}

// 转存分享链接
const handleTransferShare = async () => {
  const shareId = parseShareLink()
  if (!shareId) return
  
  transferLoading.value = true
  try {
    // 获取分享内容信息（根目录）
    const response = await filesAPI.getShareInfo(shareId, shareLinkPasscode.value)
    if (response.success && response.data) {
      shareContentInfo.value = {
        shareId: shareId,
        passcode: shareLinkPasscode.value,
        token: response.data.token,
        files: response.data.files || [],
        total_size: response.data.total_size || 0
      }
      
      // 构建树形结构
      buildShareFileTree(response.data.files)
      
      // 加载文件夹树
      await loadFolderTree()
      transferTargetFolderId.value = findPreferredRootFolderId('来自：分享') || ''
      selectedShareFileIds.value = []
      transferDialogVisible.value = true
    } else {
      ElMessage.error(response.message || '获取分享信息失败')
    }
  } catch (error: any) {
    console.error('获取分享信息失败:', error)
    ElMessage.error(error.response?.data?.detail || '获取分享信息失败')
  } finally {
    transferLoading.value = false
  }
}

// 构建分享文件树形结构
const buildShareFileTree = (files: any[]) => {
  console.log('原始文件列表:', files)
  
  if (!files || files.length === 0) {
    shareFileTree.value = []
    return
  }
  
  // 创建节点映射
  const nodeMap = new Map<string, any>()
  
  // 初始化所有节点
  files.forEach(file => {
    // 尝试多个可能的字段名来获取父目录 ID
    let parentFid = file.pdir_fid || file.parent_fid || file.dir_id || null
    
    // 标准化字段：确保 category 和 file_type 都存在
    const normalizedFile = {
      ...file,
      // 统一使用 pdir_fid 字段
      pdir_fid: parentFid,
      // 确保 category 和 file_type 都存在且一致
      category: file.category !== undefined ? file.category : (file.file_type === 0 ? 0 : 1),
      file_type: file.file_type !== undefined ? file.file_type : (file.category === 0 ? 0 : 1),
      // 文件夹需要空的 children 数组才能被懒加载
      children: (file.category === 0 || file.file_type === 0) ? [] : undefined
    }
    
    nodeMap.set(file.fid, normalizedFile)
  })
  
  // 调试：打印所有文件的信息
  files.forEach(file => {
    const node = nodeMap.get(file.fid)
    console.log(`文件：${file.file_name}, fid: ${file.fid}, share_fid_token: ${file.share_fid_token}, pdir_fid: ${node.pdir_fid}`)
  })
  
  // 检查是否存在真正的根节点（pdir_fid 为 '0' 或空）
  const hasRealRoot = files.some(file => {
    const pdirFid = file.pdir_fid || file.parent_fid || file.dir_id
    return !pdirFid || pdirFid === '0' || pdirFid === ''
  })
  
  // 构建树形结构
  const rootNodes: any[] = []
  files.forEach(file => {
    const node = nodeMap.get(file.fid)
    // 检查是否是根目录（pdir_fid 为 0、null、undefined 或空字符串）
    const isRoot = !node.pdir_fid || node.pdir_fid === '0' || node.pdir_fid === ''
    
    if (isRoot) {
      // 根节点
      rootNodes.push(node)
    } else if (hasRealRoot) {
      // 存在真正的根节点，尝试添加到父节点
      const parentNode = nodeMap.get(node.pdir_fid)
      if (parentNode) {
        parentNode.children.push(node)
      } else {
        // 如果找不到父节点，也作为根节点
        console.warn(`找不到父节点：${file.file_name}, pdir_fid: ${node.pdir_fid}`)
        rootNodes.push(node)
      }
    } else {
      // 不存在真正的根节点（用户浏览的是子目录），把所有文件作为根节点
      rootNodes.push(node)
    }
  })
  
  console.log('构建的树形结构:', rootNodes)
  shareFileTree.value = rootNodes
}

// 懒加载分享文件夹节点
const loadShareFolderNode = async (node: any, resolve: any) => {
  // 根节点直接返回已构建的树
  if (node.level === 0) {
    return resolve(shareFileTree.value)
  }
  
  const data = node.data
  console.log('加载文件夹节点:', data.file_name, 'fid:', data.fid)
  
  try {
    // 如果是文件，没有子节点
    if (data.file_type !== 0) {
      return resolve([])
    }
    
    // 如果是文件夹，加载其子内容
    const response = await filesAPI.getShareInfo(
      shareContentInfo.value.shareId,
      shareContentInfo.value.passcode,
      data.fid,  // 使用文件夹 ID 作为 pdir_fid
      shareContentInfo.value.token
    )
    
    if (response.success && response.data) {
      const childFiles = response.data.files || []
      console.log(`文件夹 "${data.file_name}" 的子内容:`, childFiles)
      
      // 为子节点构建树形结构（如果需要支持多层嵌套）
      const childNodes = childFiles.map((file: any) => ({
        ...file,
        // 确保 share_fid_token 保留
        share_fid_token: file.share_fid_token || '',
        children: file.file_type === 0 ? [] : undefined  // 文件夹有 children 字段才能展开
      }))
      
      resolve(childNodes)
    } else {
      console.error('加载子目录失败:', response.message)
      resolve([])
    }
  } catch (error) {
    console.error('加载子目录失败:', error)
    resolve([])
  }
}

// 监听树勾选变化
const handleShareFileCheckChange = () => {
  // 使用 tree ref 获取选中的节点 keys
  if (shareFileTreeRef.value) {
    selectedShareFileIds.value = shareFileTreeRef.value.getCheckedKeys(false)
    console.log('选中的文件IDs:', selectedShareFileIds.value)
  }
}

// 选择转存目标目录
const handleTransferTargetSelect = (data: any) => {
  transferTargetFolderId.value = data.id
}

// 下载分享 - 监听树勾选变化
const handleDownloadShareFileCheckChange = () => {
  if (downloadShareFileTreeRef.value) {
    selectedDownloadShareFileIds.value = downloadShareFileTreeRef.value.getCheckedKeys(false)
    console.log('下载选中的文件IDs:', selectedDownloadShareFileIds.value)
  }
}

// 选择下载目标目录
const handleDownloadTargetSelect = (data: any) => {
  downloadTargetFolderId.value = data.id
}

// 确认转存
const confirmTransfer = async () => {
  if (!shareContentInfo.value) {
    return
  }
  
  if (selectedShareFileIds.value.length === 0) {
    ElMessage.warning('请选择要转存的文件')
    return
  }
  
  transferConfirmLoading.value = true
  try {
    // 获取所有选中节点（check-strictly=false 时，选中父节点会自动选中所有子节点）
    const checkedNodes = shareFileTreeRef.value?.getCheckedNodes(false, false) || []
    
    // 过滤：如果父节点被选中，则排除其子节点（转存父目录会自动包含所有子内容）
    const selectedFids = new Set(checkedNodes.map((n: any) => n.fid))
    const itemsToTransfer = checkedNodes.filter((node: any) => {
      // 检查是否有父节点被选中（向上遍历所有祖先节点）
      let parentFid = node.pdir_fid
      while (parentFid && parentFid !== '0') {
        if (selectedFids.has(parentFid)) {
          // 父节点被选中，跳过此子节点
          return false
        }
        // 继续向上查找祖先节点
        const parentNode = checkedNodes.find((n: any) => n.fid === parentFid)
        if (parentNode) {
          parentFid = parentNode.pdir_fid
        } else {
          break
        }
      }
      return true
    })
    
    // 按目录分组转存
    const filesByDir = new Map<string, { fid: string, share_fid_token: string }[]>()
    
    itemsToTransfer.forEach((node: any) => {
      const pdirFid = node.pdir_fid || '0'
      if (!filesByDir.has(pdirFid)) {
        filesByDir.set(pdirFid, [])
      }
      filesByDir.get(pdirFid)!.push({
        fid: node.fid,
        share_fid_token: node.share_fid_token || ''
      })
    })
    
    console.log('转存项目（已过滤子节点）:', itemsToTransfer)
    console.log('按目录分组:', Object.fromEntries(filesByDir))
    
    // 依次转存每个目录的文件
    let successCount = 0
    let failCount = 0
    
    for (const [pdirFid, files] of filesByDir) {
      try {
        const fileIds = files.map(f => f.fid)
        const shareFidTokens = files.map(f => f.share_fid_token)
        
        console.log('转存参数:', {
          fileIds,
          shareFidTokens,
          pdirFid,
          token: shareContentInfo.value.token
        })
        
        const response = await filesAPI.transferShare(
          shareContentInfo.value.shareId,
          shareContentInfo.value.passcode,
          fileIds,
          shareFidTokens,
          transferTargetFolderId.value || undefined,
          pdirFid,
          shareContentInfo.value.token
        )
        
        if (response.success) {
          successCount += fileIds.length
        } else {
          failCount += fileIds.length
          console.error('转存失败:', response.message)
        }
      } catch (error: any) {
        failCount += files.length
        console.error('转存失败:', error)
      }
    }
    
    if (successCount > 0) {
      ElMessage.success(`转存成功 ${successCount} 个项目`)
      transferDialogVisible.value = false
      refreshAll()
    }
    
    if (failCount > 0) {
      ElMessage.warning(`${failCount} 个项目转存失败`)
    }
  } catch (error: any) {
    console.error('转存失败:', error)
    ElMessage.error(error.response?.data?.detail || '转存失败')
  } finally {
    transferConfirmLoading.value = false
  }
}

// 下载分享链接
const handleDownloadShare = async () => {
  const shareId = parseShareLink()
  if (!shareId) return
  
  downloadShareLoading.value = true
  try {
    // 获取分享内容信息
    const response = await filesAPI.getShareInfo(shareId, shareLinkPasscode.value)
    if (response.success && response.data) {
      shareContentInfo.value = {
        shareId: shareId,
        passcode: shareLinkPasscode.value,
        token: response.data.token,
        files: response.data.files || [],
        total_size: response.data.total_size || 0
      }
      
      // 构建树形结构
      buildShareFileTree(response.data.files)
      
      // 加载文件夹树
      await loadFolderTree()
      
      downloadTargetFolderId.value = findPreferredRootFolderId('来自：分享') || ''
      
      // 重置选中的文件
      selectedDownloadShareFileIds.value = []
      
      downloadShareDialogVisible.value = true
    } else {
      ElMessage.error(response.message || '获取分享信息失败')
    }
  } catch (error: any) {
    console.error('获取分享信息失败:', error)
    ElMessage.error(error.response?.data?.detail || '获取分享信息失败')
  } finally {
    downloadShareLoading.value = false
  }
}

// 确认下载分享内容
const confirmDownloadShare = async (mode: 'keep' | 'clean' = 'clean') => {
  if (!shareContentInfo.value) {
    return
  }
  
  if (selectedDownloadShareFileIds.value.length === 0) {
    ElMessage.warning('请选择要下载的文件')
    return
  }
  
  // 调试日志
  console.log('[DEBUG] 确认下载分享:')
  console.log('[DEBUG]   shareId:', shareContentInfo.value.shareId)
  console.log('[DEBUG]   token:', shareContentInfo.value.token)
  console.log('[DEBUG]   fileIds:', selectedDownloadShareFileIds.value)
  console.log('[DEBUG]   mode:', mode)
  console.log('[DEBUG]   targetFolderId:', downloadTargetFolderId.value)
  
  downloadShareConfirmLoading.value = true
  try {
    const response = await filesAPI.downloadShare(
      shareContentInfo.value.shareId,
      shareContentInfo.value.passcode,
      selectedDownloadShareFileIds.value,  // 使用选中的文件
      shareContentInfo.value.token,  // 传递 token
      mode,  // 传递下载模式
      downloadTargetFolderId.value || undefined  // 传递目标文件夹ID
    )
    
    if (response.success) {
      ElMessage.success(response.message || '下载任务已创建')
      downloadShareDialogVisible.value = false
    } else {
      ElMessage.error(response.message || '下载失败')
    }
  } catch (error: any) {
    console.error('下载失败:', error)
    ElMessage.error(error.response?.data?.detail || '下载失败')
  } finally {
    downloadShareConfirmLoading.value = false
  }
}

// 退出登录
const handleLogout = async () => {
  try {
    await userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/quark/login')
  } catch (error) {
    router.push('/quark/login')
  }
}

onMounted(() => {
  loadFiles()
  loadStorageInfo()
  loadUserInfo()
  // 添加全局粘贴事件监听
  document.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  // 移除粘贴事件监听
  document.removeEventListener('paste', handlePaste)
})
</script>

<style scoped>
.files-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  background: rgba(var(--quark-surface-soft-rgb) / 0.62);
  border-bottom: 1px solid rgba(var(--quark-border-rgb) / 0.32);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breadcrumb {
  margin-left: 16px;
}

.breadcrumb-container {
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
  padding: 12px 16px;
  margin-bottom: 16px;
  border-radius: 8px;
  border: 1px solid rgba(var(--quark-border-rgb) / 0.28);
  box-shadow: 0 4px 12px rgba(var(--app-shadow-rgb) / 0.04);
}

.breadcrumb-container :deep(.el-breadcrumb) {
  font-size: 14px;
}

.breadcrumb-container :deep(.el-breadcrumb__item) {
  cursor: pointer;
}

.breadcrumb-container :deep(.el-breadcrumb__inner) {
  color: rgb(var(--quark-text-muted-rgb));
  font-weight: 500;
  transition: color 0.2s;
}

.breadcrumb-container :deep(.el-breadcrumb__item:hover .el-breadcrumb__inner) {
  color: rgb(var(--quark-primary-rgb));
}

.breadcrumb-container :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: rgb(var(--quark-primary-rgb));
  font-weight: 600;
}

.breadcrumb-container :deep(.el-breadcrumb__separator) {
  color: rgb(var(--quark-text-subtle-rgb));
  margin: 0 8px;
}

.main {
  background: rgba(var(--quark-bg-soft-rgb) / 0.88);
  padding: 20px;
  flex: 1;
  overflow: auto;
  position: relative;
}

.main.is-dragging {
  background: rgba(var(--quark-primary-rgb) / 0.06);
}

.drag-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(var(--quark-primary-rgb) / 0.08);
  border: 2px dashed rgba(var(--quark-accent-rgb) / 0.42);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  pointer-events: none;
}

.drag-overlay-content {
  text-align: center;
  color: rgb(var(--quark-primary-rgb));
}

.drag-overlay-content p {
  margin-top: 12px;
  font-size: 16px;
  font-weight: 500;
}

.toolbar {
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
  padding: 10px 16px;
  margin-bottom: 16px;
  border-radius: 4px;
  border: 1px solid rgba(var(--quark-border-rgb) / 0.28);
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-list-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  font-size: 13px;
  color: rgb(var(--quark-text-muted-rgb));
  background: rgba(var(--quark-primary-rgb) / 0.06);
  border: 1px dashed rgba(var(--quark-accent-rgb) / 0.32);
  border-radius: 8px;
}

.file-list-hint .el-icon {
  color: rgb(var(--quark-primary-rgb));
  font-size: 16px;
}

.selected-info {
  color: rgb(var(--quark-primary-rgb));
  font-weight: 500;
}

.sortable-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sort-buttons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  line-height: 1;
}

.sort-buttons .el-button {
  padding: 0;
  width: 14px;
  height: 12px;
  font-size: 10px;
  border: none;
  background: transparent;
  color: #c0c4cc;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
}

.sort-buttons .el-button:hover {
  background: #f5f7fa;
  color: #909399;
}

.sort-buttons .el-button.is-active {
  color: rgb(var(--quark-primary-rgb));
}

.sort-buttons .el-button .el-icon {
  font-size: 10px;
  margin: 0;
}

.upload-content {
  padding: 10px 0;
}

.upload-drop-zone {
  border: 2px dashed rgba(var(--quark-border-rgb) / 0.42);
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: rgba(var(--quark-surface-soft-rgb) / 0.42);
}

.upload-drop-zone:hover {
  border-color: rgb(var(--quark-primary-rgb));
  background: rgba(var(--quark-primary-rgb) / 0.06);
}

.upload-drop-zone.is-dragging {
  border-color: rgb(var(--quark-accent-rgb));
  background: rgba(var(--quark-primary-rgb) / 0.1);
}

.upload-icon {
  color: rgb(var(--quark-text-subtle-rgb));
  margin-bottom: 12px;
}

.upload-drop-zone:hover .upload-icon {
  color: rgb(var(--quark-primary-rgb));
}

.upload-drop-zone.is-dragging .upload-icon {
  color: rgb(var(--quark-accent-rgb));
}

.upload-text {
  font-size: 16px;
  color: rgb(var(--quark-text-rgb));
  margin: 0 0 8px 0;
}

.upload-location-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: rgb(var(--quark-text-subtle-rgb));
}

.upload-task-panel {
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 360px;
  max-height: 420px;
  background: rgba(var(--quark-surface-rgb) / 0.96);
  border: 1px solid rgba(var(--quark-border-rgb) / 0.42);
  border-radius: 12px;
  box-shadow: 0 12px 28px rgba(var(--app-shadow-rgb) / 0.09);
  z-index: 2200;
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
}

.upload-task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid rgba(var(--quark-border-rgb) / 0.22);
}

.upload-task-title {
  font-size: 14px;
  font-weight: 700;
  color: rgb(var(--quark-text-rgb));
}

.upload-task-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--quark-text-subtle-rgb));
}

.upload-task-list {
  overflow-y: auto;
  padding: 8px 10px 12px;
}

.upload-task-item {
  padding: 10px 8px;
  border-radius: 10px;
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
}

.upload-task-item + .upload-task-item {
  margin-top: 8px;
}

.upload-task-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.upload-task-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--quark-text-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.upload-task-status {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
}

.upload-task-status.is-waiting {
  color: #6b7280;
}

.upload-task-status.is-uploading {
  color: #2563eb;
}

.upload-task-status.is-success {
  color: #16a34a;
}

.upload-task-status.is-error {
  color: #dc2626;
}

.upload-task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: rgb(var(--quark-text-subtle-rgb));
}

@media (max-width: 768px) {
  .upload-task-panel {
    right: 12px;
    left: 12px;
    bottom: 12px;
    width: auto;
    max-height: 40vh;
  }
}

.upload-hint {
  font-size: 12px;
  color: rgb(var(--quark-text-subtle-rgb));
  margin: 0 0 16px 0;
}

.upload-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.upload-file-list {
  margin-top: 16px;
  border: 1px solid rgba(var(--quark-border-rgb) / 0.32);
  border-radius: 4px;
  overflow: hidden;
}

.upload-file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
  border-bottom: 1px solid rgba(var(--quark-border-rgb) / 0.22);
  font-size: 13px;
  color: rgb(var(--quark-text-muted-rgb));
}

.upload-file-items {
  max-height: 200px;
  overflow-y: auto;
  padding: 8px 12px;
}

.upload-file-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--quark-border-rgb) / 0.16);
}

.upload-file-item:last-child {
  border-bottom: none;
}

.upload-file-item .file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-file-item .file-size {
  color: rgb(var(--quark-text-subtle-rgb));
  font-size: 12px;
  margin-left: 10px;
  margin-right: 8px;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.folder-icon {
  font-size: 20px;
}

.file-icon {
  font-size: 20px;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clickable {
  cursor: pointer;
}

.clickable:hover {
  color: rgb(var(--quark-primary-rgb));
}

.folder-size {
  color: rgb(var(--quark-text-subtle-rgb));
}

.footer {
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
  border-top: 1px solid rgba(var(--quark-border-rgb) / 0.32);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 40px;
}

.footer-right {
  display: flex;
  align-items: center;
}

.storage-info {
  text-align: center;
  padding: 20px;
}

.storage-text {
  font-size: 24px;
  font-weight: bold;
  display: block;
}

.storage-total {
  font-size: 14px;
  color: rgb(var(--quark-text-subtle-rgb));
}

.storage-detail {
  margin-top: 20px;
  text-align: left;
}

.storage-detail p {
  margin: 8px 0;
  color: rgb(var(--quark-text-muted-rgb));
}

.share-info {
  padding: 10px 0;
}

.share-options {
  padding: 10px 0;
}

.share-options h4 {
  margin: 0 0 15px 0;
  color: rgb(var(--quark-text-muted-rgb));
}

.share-link-box {
  width: 100%;
  text-align: left;
}

.passcode-box {
  margin-top: 15px;
  display: flex;
  align-items: center;
}

.passcode-label {
  font-size: 14px;
  color: rgb(var(--quark-text-muted-rgb));
}

.move-dialog-content {
  max-height: 400px;
  overflow-y: auto;
}

.tree-node {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(var(--quark-surface-rgb) / 0.82);
  box-shadow: 0 2px 8px rgba(var(--app-shadow-rgb) / 0.08);
}

.user-avatar-placeholder {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgb(var(--quark-primary-rgb));
  color: white;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 20px;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-weight: 500;
  color: rgb(var(--quark-text-rgb));
  font-size: 14px;
}

.user-storage {
  font-size: 12px;
  color: rgb(var(--quark-text-subtle-rgb));
}

.storage-bar {
  width: 120px;
  margin-left: 8px;
}

.share-link-section {
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
  padding: 12px 20px;
  border-bottom: 1px solid rgba(var(--quark-border-rgb) / 0.28);
  display: flex;
  align-items: center;
  gap: 16px;
}

.share-link-input {
  display: flex;
  align-items: center;
  flex: 1;
}

.share-link-actions {
  display: flex;
  gap: 8px;
}

.transfer-dialog-content {
  max-height: 500px;
  overflow-y: auto;
}

.share-content-info {
  margin-bottom: 15px;
}

.share-content-info h4 {
  margin: 0 0 10px 0;
  color: rgb(var(--quark-text-muted-rgb));
}

.share-content-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid rgba(var(--quark-border-rgb) / 0.28);
  border-radius: 4px;
  padding: 8px;
}

.share-content-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(var(--quark-border-rgb) / 0.16);
}

.share-content-item:last-child {
  border-bottom: none;
}

.share-content-item .file-size {
  margin-left: auto;
  color: rgb(var(--quark-text-subtle-rgb));
  font-size: 12px;
}

.download-share-content {
  max-height: 400px;
  overflow-y: auto;
}
</style>
