// Encode generated artwork for local/offline delivery, retaining alpha.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const ffmpeg=require('ffmpeg-static');
const directory=path.resolve(__dirname,'../voting-system/static/assets');
for(const name of ['hero-vote','login-vote','example-entries','example-choice','example-projects']){
  const input=path.join(directory,name+'.png'),output=path.join(directory,name+'.webp');
  if(!fs.existsSync(input))continue;
  const result=spawnSync(ffmpeg,['-y','-i',input,'-vf','scale=960:-1','-c:v','libwebp','-quality','88','-compression_level','6',output],{encoding:'utf8'});
  if(result.status!==0)throw Error(result.stderr);
  console.log(name,fs.statSync(output).size);
}
