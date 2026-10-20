FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci


# Vite dev server with HMR. docker-compose selects this with `target: dev`.
FROM deps AS dev

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


FROM deps AS build

# Vite inlines VITE_* values into the bundle at build time, so the API URL must
# be supplied here rather than at container start.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY . .
RUN npm run build


# Default target: static files behind nginx, no Node in the final image.
# The unprivileged variant runs as non-root and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
