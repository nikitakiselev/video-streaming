FROM caddy:2-alpine

WORKDIR /srv

COPY Caddyfile /etc/caddy/Caddyfile
COPY public /srv/public

EXPOSE 80

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile"]

