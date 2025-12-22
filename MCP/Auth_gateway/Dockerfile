FROM openresty/openresty:alpine

RUN rm -f /usr/local/openresty/nginx/conf/conf.d/default.conf

# Replace default nginx.conf with ours
COPY nginx.conf /usr/local/openresty/nginx/conf/nginx.conf

# Expose port
EXPOSE 8081

CMD ["openresty", "-g", "daemon off;"]
