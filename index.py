#coding:UTF-8

"""
文件同步小工具
@author:yubang
2015-05-28
"""

from threading import Thread
from config import server,base
import os,ftplib,time,sqlite3,logging,re
import pyinotify,shutil


def sqlDeal(value):
    value=value.replace("'","\\'").replace("\"","\\\"")
    return value


def executeSql(sql,selectSign):
    "执行sql语句"
    conn = sqlite3.connect('data/file.db')
    cursor = conn.cursor()
    cursor.execute(sql)
    if selectSign :
        r=cursor.fetchall()
    else:
        r=cursor.rowcount
    cursor.close()
    conn.commit()
    conn.close()
    return r


class SendWorker(Thread):
    "文件传送类"
    def __moveSuccessUploadFile(self,filePath):
        "移动上传成功的文件"
        oldPath=filePath
        filePath=filePath.replace(base.monitorPath,"")
        if filePath[0] != "/":
            filePath="/"+filePath
        targetFile=base.move_dir+filePath
        targetDir=os.path.dirname(targetFile)
        if not os.path.exists(targetDir):
            os.makedirs(targetDir)
        try:
            shutil.move(oldPath,targetFile)
            logging.info(u"文件%s -> %s 移动成功！"%(oldPath,targetFile))
        except:
            logging.error(u"文件%s -> %s 移动失败！"%(oldPath,targetFile))
    def __handle(self,filePath):
        "处理要上传的文件"
        result=True
        for obj in server.serverLists:
            remotePath=self.__getRemotePath(filePath,obj['data']['ftpRootPrefix'])
            r=self.__sendFileUseFtp(obj['data']['ftpHost'],obj['data']['ftpPort'],obj['data']['ftpUser'],obj['data']['ftpPassword'],filePath,remotePath)
            if not r:
                result = False
                logging.error(u"文件（%s）上传服务器（%s）失败！"%(filePath,obj['data']['ftpHost']))
            else:
                logging.info(u"文件（%s）上传服务器（%s）成功！"%(filePath,obj['data']['ftpHost']))
        if result and base.move_able:
            #移动上传后的文件
            self.__moveSuccessUploadFile(filePath)
    def __getRemotePath(self,filePath,remotePath):
        "获取远程服务器文件存放路径"
        filePath=filePath.replace(base.monitorPath,"")
        if filePath[0] != "/":
            filePath="/"+filePath
        filePath=remotePath+filePath
        filePath=os.path.dirname(filePath)
        return filePath
    def __sendFileUseFtp(self,serverHost,serverPort,serverUser,serverPassword,filePath,remotePath):
        "发送文件"
        result = True
        ftp=ftplib.FTP()
        ftp.connect(serverHost,serverPort)
        r=ftp.login(serverUser,serverPassword)
        if r == "230 Login successful.":
            fp = open(filePath,"r")
            
            #递归在ftp服务器创建文件夹
            remotePaths=remotePath.split("/")
            tempPath="."
            for t in remotePaths:
                tempPath+="/"+t
                try:
                    ftp.mkd(tempPath)
                except:
                    logging.info(u"在ftp服务器（%s）创建文件夹失败"%(serverHost))
            
            try:
                ftp.cwd(remotePath)
                ftp.storbinary('STOR %s' % os.path.basename(filePath),fp,1024)
            except:
                logging.error(u"在ftp服务器（%s）上传文件失败"%(serverHost))
                result=False
            fp.close()
        else:
            result=False
        ftp.quit()
        return result
        
    def run(self):
        while True:
            fps=executeSql("select * from files where status = 0 limit 1",True)
            if len(fps) == 0:
                time.sleep(1.5)
            else:
                try:
                    self.__handle(fps[0][0])
                except Exception,e:
                    #raise
                    logging.error(str(e))
                    time.sleep(1.5)
                executeSql("update files set status = 1 where path = '%s'"%(fps[0][0]),True)


class MyEventHandler(pyinotify.ProcessEvent):
    "监控处理类"
    def __checkAbleFile(self,filename):
        "检测文件是否需要转移"
        for r in base.able_lists:
            if re.search("\."+r+"$",filename):
                return True
        return False
    def process_IN_CLOSE_WRITE(self, event):
        filePath=os.path.join(event.path,event.name)
        if self.__checkAbleFile(event.name):
            logging.info(u"检测到要上传文件:"+filePath)
            executeSql("insert into files(path,status) values('%s',0)"%sqlDeal(filePath),False)
        else:
            logging.warning(u"检测到不符合规则文件:%s"%(filePath))
            
def init():
    "初始化"
    executeSql("create table if not exists files(path varchar(255),status int(1))",False)
    
    logging.basicConfig(filename = "log/tmp.log",level = logging.NOTSET, format = '%(asctime)s - %(levelname)s: %(message)s' )
    
    sendWorker=SendWorker()
    sendWorker.setDaemon(True)
    sendWorker.start()    
      
        
def main():
    "主函数"
    
    init()
    
    wm = pyinotify.WatchManager()
    wm.add_watch(base.monitorPath, pyinotify.ALL_EVENTS, rec=True)
    eh = MyEventHandler()
    notifier = pyinotify.Notifier(wm, eh)
    notifier.loop()
    
    
if __name__ == "__main__":
    main()
