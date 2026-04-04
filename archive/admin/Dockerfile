# 多阶段构建：构建阶段
FROM node:20-alpine AS build

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖（包括devDependencies，因为构建需要TypeScript和Vite）
RUN npm ci

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 复制构建产物到nginx目录
COPY --from=build /app/dist /usr/share/nginx/html

# 复制自定义nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 5173

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]