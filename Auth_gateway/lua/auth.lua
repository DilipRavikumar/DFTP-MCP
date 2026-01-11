local ck = require "resty.cookie"
local cookie, err = ck:new()
if not cookie then
    ngx.status = ngx.HTTP_INTERNAL_SERVER_ERROR
    ngx.say("Cookie error: "..err)
    return ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

local access_token = cookie:get("access_token")

if not access_token then
    ngx.status = ngx.HTTP_UNAUTHORIZED
    ngx.say("Unauthorized - Token missing")
    return ngx.exit(ngx.HTTP_UNAUTHORIZED)
end

-- Optional: Validate JWT
-- local jwt = require "resty.jwt"
-- local jwt_obj = jwt:verify("your_public_key", access_token)
-- if not jwt_obj["verified"] then
--     ngx.status = ngx.HTTP_UNAUTHORIZED
--     ngx.say("Unauthorized - Invalid token")
--     return ngx.exit(ngx.HTTP_UNAUTHORIZED)
-- end

-- Allow request
