FROM node:18-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
# Use legacy-peer-deps to avoid peer dependency resolution failures inside build containers
RUN npm ci --include=dev --legacy-peer-deps || npm install --include=dev --legacy-peer-deps
COPY . .
# VITE_BACKEND_URL is baked into the JS bundle at build time, not runtime
ARG VITE_BACKEND_URL=http://localhost:8000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

