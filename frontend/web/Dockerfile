FROM node:20-alpine

WORKDIR /app

# Installed separately first so `npm ci` is only re-run when package*.json
# actually changes, not on every source edit.
COPY package*.json ./
RUN npm ci

COPY . .

# Not a long-running server: this image's only job is to compile the React
# app. docker-compose runs it once (mounting the real source over /app and
# writing the build output straight to the host's frontend/dist), then the
# app service starts once this container exits successfully.
CMD ["npm", "run", "build"]
