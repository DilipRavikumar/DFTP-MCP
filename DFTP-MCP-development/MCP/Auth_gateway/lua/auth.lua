local auth = ngx.var.http_authorization

if not auth or auth == "" then
    ngx.status = ngx.HTTP_UNAUTHORIZED
    ngx.say("Unauthorized - Token missing")
    return ngx.exit(ngx.HTTP_UNAUTHORIZED)
end

-- OPTIONAL JWT validation can be added here

-- Allow request
