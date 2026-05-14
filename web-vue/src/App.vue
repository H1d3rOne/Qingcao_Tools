<script setup lang="ts">
</script>

<template>
  <div class="app-shell">
    <div class="ambient-blob ambient-blob--green" aria-hidden="true" />
    <div class="ambient-blob ambient-blob--teal" aria-hidden="true" />
    <div class="ambient-blob ambient-blob--emerald" aria-hidden="true" />
    <router-view />
  </div>
</template>

<style>
#app {
  width: 100%;
  height: 100%;
}

.app-shell {
  position: relative;
  width: 100%;
  min-height: 100vh;
}

.app-shell > .ambient-blob {
  position: fixed;
  z-index: 0;
}
</style>
