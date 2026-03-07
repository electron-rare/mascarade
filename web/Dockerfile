FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG CRAZY_LIFE_BASE=/
ENV CRAZY_LIFE_BASE="${CRAZY_LIFE_BASE}"

RUN npm run build

FROM nginx:1.29-alpine

COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

