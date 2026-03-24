# DEPLOY — DizelTrade Web App v2 (Wizard)

## Структура файлов

/opt/DizelTrade/
├── dizeltrade-key.json     # уже есть
├── .env                    # уже есть
├── venv/                   # уже есть
└── web_app/
    ├── app.py
    └── templates/
        ├── login.html
        ├── menu.html
        └── wizard.html


## 1. Скопировать файлы

mkdir -p /opt/DizelTrade/web_app/templates
cp app.py /opt/DizelTrade/web_app/
cp templates/* /opt/DizelTrade/web_app/templates/


## 2. Добавить в .env

WEB_APP_PASSWORD=ваш_пароль
FLASK_SECRET_KEY=любые32+символаслучайно


## 3. Установить Flask

cd /opt/DizelTrade
source venv/bin/activate
pip install flask --break-system-packages


## 4. Systemd сервис

cat > /etc/systemd/system/dizeltrade-web.service << 'EOF'
[Unit]
Description=DizelTrade Web App
After=network.target

[Service]
User=root
WorkingDirectory=/opt/DizelTrade/web_app
Environment=PATH=/opt/DizelTrade/venv/bin
ExecStart=/opt/DizelTrade/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dizeltrade-web
systemctl start dizeltrade-web


## 5. Nginx

cat > /etc/nginx/sites-available/dizeltrade-web << 'EOF'
server {
    listen 80;
    server_name form.dizelfinance.run.place;
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/dizeltrade-web /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx


## 6. HTTPS

certbot --nginx -d form.dizelfinance.run.place


## Управление

systemctl restart dizeltrade-web
journalctl -u dizeltrade-web -f
