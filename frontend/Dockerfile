FROM node:22-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

# TLS inceleyen kurumsal ağlar için ek kök sertifikalar (bkz. certs/README.md).
# Dizin yalnızca README içeriyorsa bu adım hiçbir şey değiştirmez.
COPY certs/ /usr/local/share/ca-certificates/kavun/
RUN cat /usr/local/share/ca-certificates/kavun/*.crt >> /etc/ssl/certs/ca-certificates.crt 2>/dev/null || true

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# Geliştirme ortamı: hot-reload açık (CLAUDE.md §6).
CMD ["npm", "run", "dev"]
