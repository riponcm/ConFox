/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DASH0_ENDPOINT?: string
  readonly VITE_DASH0_TOKEN?: string
  readonly VITE_DASH0_DATASET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
