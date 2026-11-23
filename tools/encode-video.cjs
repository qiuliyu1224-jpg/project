const {spawnSync}=require('node:child_process');
const ffmpeg=require('ffmpeg-static');
const [input,output]=process.argv.slice(2);
if(!input||!output)throw Error('Usage: npm run video:encode -- input.webm output.mp4');
const result=spawnSync(ffmpeg,['-y','-i',input,'-c:v','libx264','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart','-an',output],{stdio:'inherit'});
process.exitCode=result.status??1;
