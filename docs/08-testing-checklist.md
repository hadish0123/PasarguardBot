# End-to-End Testing Checklist

## Central
- [ ] start
- [ ] register valid bot
- [ ] reject invalid token
- [ ] approve representative
- [ ] provision tenant
- [ ] disable representative
- [ ] restart runtime

## Representative Admin
- [ ] open admin panel
- [ ] dashboard
- [ ] plans list
- [ ] create volume plan
- [ ] create fair-use plan
- [ ] create unlimited plan
- [ ] edit plan
- [ ] disable/enable plan
- [ ] users
- [ ] user details
- [ ] sales settings
- [ ] discount create/edit/delete
- [ ] texts/buttons
- [ ] logs
- [ ] ready links
- [ ] settings

## Representative User
- [ ] start
- [ ] home
- [ ] buy service
- [ ] select panel
- [ ] select plan
- [ ] custom volume
- [ ] custom duration
- [ ] discount
- [ ] username
- [ ] payment
- [ ] service creation
- [ ] my services
- [ ] service details
- [ ] wallet
- [ ] transactions
- [ ] profile
- [ ] support
- [ ] referral
- [ ] trial

## Isolation
- [ ] User A cannot see Tenant B data.
- [ ] Admin A cannot edit Tenant B plans.
- [ ] Tenant A state does not leak into Tenant B.
- [ ] Tenant-specific Panel credentials are used.
- [ ] Central DB is not accidentally used for Tenant business queries.

## Runtime quality
- [ ] no unresolved handler filter errors
- [ ] no Redis scheme/config errors
- [ ] no unhandled StopPropagation traces
- [ ] clean startup
- [ ] clean shutdown
- [ ] restart recovery
