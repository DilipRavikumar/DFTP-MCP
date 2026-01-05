FROM openresty/openresty:alpine

# Remove default site
RUN rm -f /usr/local/openresty/nginx/conf/conf.d/default.conf

# Copy nginx.conf
COPY nginx.conf /usr/local/openresty/nginx/conf/nginx.conf

# Copy Lua scripts
COPY lua/ /lua/

EXPOSE 8081

CMD ["openresty", "-g", "daemon off;"]
