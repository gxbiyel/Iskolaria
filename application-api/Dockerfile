FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM base AS test
RUN npm test

FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev
COPY src ./src
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s \
    CMD wget -qO- http://localhost:3000/health || exit 1
USER node
CMD ["node", "src/server.js"]