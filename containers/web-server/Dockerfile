FROM nginx:1.25-alpine
LABEL description="DIC Patient Web Portal — nginx with audited login events"

RUN apk add --no-cache python3 py3-pip curl bash

RUN pip3 install --no-cache-dir flask --break-system-packages 2>/dev/null || \
    pip3 install --no-cache-dir flask

COPY default.conf /etc/nginx/conf.d/default.conf
COPY index.html   /var/www/html/index.html
COPY portal.py    /opt/portal.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /var/log/nginx /var/log/portal

EXPOSE 80 8888

ENTRYPOINT ["/entrypoint.sh"]
