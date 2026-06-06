## 干饭情报局 - 宝塔面板部署指南

### 一、上传代码到服务器

1. 把整个 `ganfan` 项目文件夹压缩成 zip
2. 宝塔面板 -> 文件 -> 上传到 `/www/wwwroot/ganfan/`（或你喜欢的路径）
3. 解压到该目录

### 二、安装宝塔插件

1. 宝塔面板 -> 软件商店
2. 搜索 **Python项目管理器**，点击安装
3. 搜索 **Nginx**（一般已装好）

### 三、创建 MySQL 数据库

1. 宝塔面板 -> 数据库 -> 添加数据库
   - 数据库名：`caidan`
   - 用户名：`caidan`（不要用 root）
   - 密码：自己设一个强密码，记住它
   - 编码：`utf8mb4`
2. 点击刚创建的数据库右边的 **导入**，把你本地的数据库导出 SQL 导入进去
   - 本地导出方法：在你电脑命令行执行
     ```
     mysqldump -u root -proot caidan > caidan_backup.sql
     ```
   - 把 `caidan_backup.sql` 上传到服务器，然后在宝塔里导入

### 四、用 Python 项目管理器创建项目

1. 宝塔面板 -> Python项目管理器 -> 添加项目
2. 填写以下信息：
   - **项目名称**：`ganfan`
   - **项目路径**：`/www/wwwroot/ganfan`
   - **启动文件**：`guigong_mall/wsgi.py`（或选 manage.py）
   - **Python版本**：选 3.8 或更高
   - **运行框架**：选 `Django`（或 Gunicorn）
   - **端口**：`8000`
   - **是否开机启动**：是
3. 点击提交，管理器会自动创建虚拟环境并安装依赖

### 五、安装依赖

如果 Python 项目管理器没有自动安装依赖，手动操作：

1. 在 Python 项目管理器中找到 `ganfan` 项目
2. 点击 **模块** -> **安装模块**
3. 选择从 `requirements.txt` 安装，或直接安装以下包：
   ```
   Django==4.2.11
   Pillow==10.2.0
   PyMySQL==1.1.1
   PyJWT==2.8.0
   gunicorn==21.2.0
   whitenoise==6.6.0
   ```

### 六、设置环境变量

在 Python 项目管理器中，给项目添加以下环境变量：

| 变量名 | 值 | 说明 |
|---|---|---|
| `DJANGO_SECRET_KEY` | （生成一个随机字符串，见下方） | Django 安全密钥 |
| `DJANGO_DEBUG` | `False` | 关闭调试模式 |
| `DJANGO_ALLOWED_HOSTS` | `你的域名或IP` | 例如 `ganfan.example.com` 或 `123.45.67.89` |
| `DB_NAME` | `caidan` | 数据库名 |
| `DB_USER` | `caidan` | 数据库用户名 |
| `DB_PASSWORD` | `你设的密码` | 数据库密码 |
| `DB_HOST` | `localhost` | 数据库地址 |
| `DB_PORT` | `3306` | 数据库端口 |

生成随机 SECRET_KEY 的方法（在你电脑命令行执行）：
```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 七、执行数据库迁移和收集静态文件

通过 SSH 连接服务器，进入项目虚拟环境：

```bash
cd /www/wwwroot/ganfan
# 激活虚拟环境（路径以实际为准）
source /www/wwwroot/ganfan/venv/bin/activate

# 执行迁移
python manage.py migrate

# 收集静态文件
python manage.py collectstatic --noinput
```

### 八、配置 Nginx 反向代理

1. 宝塔面板 -> 网站 -> 添加站点
   - 域名：填你的域名或 IP
   - 根目录：`/www/wwwroot/ganfan`
   - PHP版本：选 **纯静态**
2. 点击刚创建的站点 -> **反向代理** -> 添加反向代理
   - 代理名称：`ganfan`
   - 目标URL：`http://127.0.0.1:8000`
   - 发送域名：`$host`
3. 点击 **配置文件**，在 `location /` 块之前加上媒体文件代理：
   ```nginx
   location /media/ {
       alias /www/wwwroot/ganfan/media/;
       expires 30d;
       access_log off;
   }
   ```
4. 保存配置，重载 Nginx

### 九、设置媒体文件目录权限

SSH 执行：
```bash
chown -R www:www /www/wwwroot/ganfan/media
chmod -R 755 /www/wwwroot/ganfan/media
```

### 十、配置 SSL 证书（推荐）

1. 宝塔面板 -> 网站 -> 你的站点 -> SSL
2. 选 **Let's Encrypt** 免费证书，申请即可
3. 开启 **强制 HTTPS**

### 验证部署

浏览器访问你的域名，应该能看到干饭情报局首页。访问 `/admin/` 进入管理后台。

### 常见问题

**Q: 页面显示 502 Bad Gateway**
- 检查 Python 项目是否正常运行（Python项目管理器中查看状态）
- 检查端口 8000 是否在监听：`ss -tlnp | grep 8000`

**Q: 静态文件（CSS/JS）加载不了**
- 确认执行过 `collectstatic`
- 确认 Nginx 反向代理配置正确

**Q: 图片上传失败**
- 检查 `media` 目录权限是否为 `www:www`
- 检查 Nginx 配置中 `client_max_body_size` 是否够大（建议 10M）

**Q: 数据库连接失败**
- 检查环境变量 DB_* 是否正确
- 检查 MySQL 是否运行
- 检查数据库用户权限
