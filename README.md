# luBoard——XCPC比赛本地实时榜单软件

## 目前已有功能：

1. 本地导入榜单 

2. 定时启动启动榜单，然后自动随时间展现榜单
3. 支持封榜
4. 在线加入新队伍、新提交记录



## 如何使用：

##### 快速环境部署指令(请使用bash或者powershell)：

```shell
#请确保您的电脑中有python环境
git clone https://github.com/Mrlaolu/luBoard.git

#进入到项目路径
cd luBoard

#安装flask框架
pip install flask

#运行使用软件
flask run

#如没有更改链接和端口，浏览器访问localhost:5000就能看到榜单了
```



##### 更换榜单

项目内自带一个Demo榜单，如需更换成其他榜单，请将项目中的contest.dat换成其他Codeforce Gym Ghost（.dat）格式的榜单



## TODO LIST

- [ ] 如XCPC BOARD一样有主页功能，能导入多个榜单
- [ ] 开放账号注册功能，每个账号都能独立导入榜单，独立使用榜单
- [ ] 加入代码打印功能，能远程操纵服务器所连接的打印机进行打印 参考DomJudge的打印功能
- [ ] 美化界面 
- [ ] 优化操作手感
- [ ] 改进展现延迟  

