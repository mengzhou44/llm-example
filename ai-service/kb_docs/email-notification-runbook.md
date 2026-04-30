# Email Notification System — Runbook

## Architecture Overview
Email notifications are processed via a background job queue (Redis + Sidekiq). The pipeline is:
  User action → Event published to Redis queue → Sidekiq worker picks up → SendGrid API call → Delivery

## Common Delay Causes

### Queue Backlog
**Symptom:** Emails delayed by minutes to hours across all users.
**Cause:** Sidekiq worker count is insufficient during traffic spikes.
**Resolution:**
1. Check `sidekiq_queues` in the metrics dashboard: look for `mailer` queue depth > 500.
2. Scale Sidekiq workers horizontally: `heroku scale worker=4` (or equivalent).
3. Check for failed jobs that are consuming retry slots: `Sidekiq::RetrySet.new.size`.

### SendGrid Rate Limiting
**Symptom:** Emails delayed only during peak hours.
**Cause:** SendGrid free/starter tier has a per-minute throughput limit.
**Resolution:**
1. Check SendGrid Activity feed for `429 Too Many Requests` responses.
2. Upgrade SendGrid plan or implement exponential backoff in the mailer worker.
3. Enable SendGrid's event webhook to track delivery vs. queue times.

### Worker Crash / Dead Queue
**Symptom:** No emails delivered for an extended period; Sidekiq UI shows 0 active workers.
**Resolution:**
1. Restart Sidekiq workers: `systemctl restart sidekiq` or redeploy worker dynos.
2. Check worker logs for OOM kills or uncaught exceptions.
3. Re-queue dead jobs from Sidekiq Dead Set if the retry count was exhausted.

### Redis Connection Timeout
**Symptom:** Sporadic email delays; Redis error logs showing connection timeouts.
**Resolution:**
1. Check Redis memory usage — if > 80%, increase instance size or flush expired keys.
2. Check network latency between the app server and Redis instance.
3. Enable Redis persistence (`appendonly yes`) to survive restarts without losing queued jobs.

## Monitoring
- Alert threshold: `mailer` queue depth > 200 for > 5 minutes.
- SLA: Transactional emails (password reset, order confirmation) must deliver within 60 seconds.
- On-call runbook: If queue depth exceeds 1000, page the on-call engineer immediately.

## Testing
To test the notification pipeline end-to-end in staging:
```
rake notify:test_email[user@example.com]
```
This enqueues a test email and logs the job ID so you can trace it through the queue.
