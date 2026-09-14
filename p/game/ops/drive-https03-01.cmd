@echo off
set PATH=%PATH%;C:\Users\Administrator\AppData\Roaming\npm
cd /d C:\Users\Administrator
echo [%date% %time%] START >> C:\Users\Administrator\ops\https03-drive.out.log
call C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd agent --agent main --message-file C:\Users\Administrator\ops\task-20260817-https03.md >> C:\Users\Administrator\ops\https03-drive.out.log 2>> C:\Users\Administrator\ops\https03-drive.err.log
echo [%date% %time%] END >> C:\Users\Administrator\ops\https03-drive.out.log
