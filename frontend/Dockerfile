FROM node:18-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
# Use legacy-peer-deps to avoid peer dependency resolution failures inside build containers
RUN npm ci --silent --legacy-peer-deps || npm install --legacy-peer-deps
COPY . .
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

