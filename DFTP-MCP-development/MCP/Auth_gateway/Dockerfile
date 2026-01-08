FROM openresty/openresty:alpine
RUN rm -f /usr/local/openresty/nginx/conf/conf.d/default.conf
COPY nginx.conf /usr/local/openresty/nginx/conf/nginx.conf
COPY lua/ /lua/
EXPOSE 8081
CMD ["openresty", "-g", "daemon off;"]
