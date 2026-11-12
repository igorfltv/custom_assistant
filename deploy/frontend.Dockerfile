FROM node:22-alpine AS build
WORKDIR /source
COPY package.json package-lock.json ./
COPY packages ./packages
COPY landing ./landing
COPY workspace ./workspace
COPY admin ./admin
RUN npm ci --no-audit --no-fund
ARG APP_NAME
RUN npm run build --workspace @forma/${APP_NAME}
FROM nginx:1.28-alpine
ARG APP_NAME
COPY deploy/static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /source/${APP_NAME}/dist /usr/share/nginx/html
EXPOSE 8080
