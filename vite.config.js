import {defineConfig} from 'vite';
import {resolve} from 'node:path';
export default defineConfig({base:process.env.GITHUB_PAGES==='true'?`/${process.env.GITHUB_REPOSITORY?.split('/')[1]||'codeverse'}/`:'/',build:{target:'es2022',rollupOptions:{input:{main:resolve('index.html'),onboarding:resolve('github-start.html'),explorer:resolve('city-explorer.html')}}},server:{host:true,allowedHosts:['terminal.local'],proxy:{"/api":"http://127.0.0.1:8000"}}});
