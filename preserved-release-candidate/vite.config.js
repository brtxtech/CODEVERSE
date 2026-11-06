import {defineConfig} from 'vite';
export default defineConfig({base:process.env.GITHUB_PAGES==='true'?`/${process.env.GITHUB_REPOSITORY?.split('/')[1]||'codeverse'}/`:'/',build:{target:'es2022'},server:{host:true}});
