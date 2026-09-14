@echo off
set PATH=%PATH%;C:\Users\Administrator\AppData\Roaming\npm
cd /d C:\Users\Administrator
echo [%date% %time%] START2 >> C:\Users\Administrator\ops\ph3-drive.out.log
call C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd agent --agent main --message-file C:\Users\Administrator\ops\task-20260817-markets-ph3.md >> C:\Users\Administrator\ops\ph3-drive.out.log 2>> C:\Users\Administrator\ops\ph3-drive.err.log
echo [%date% %time%] END2 >> C:\Users\Administrator\ops\ph3-drive.out.log
