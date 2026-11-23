const path=require('node:path'),{spawnSync}=require('node:child_process');
process.env.PLAYWRIGHT_BROWSERS_PATH??=path.resolve(__dirname,'../node_modules/.cache/ms-playwright');
const cli=require.resolve('playwright/cli');
const result=spawnSync(process.execPath,[cli,'install','chromium'],{stdio:'inherit',env:process.env});
process.exitCode=result.status??1;
