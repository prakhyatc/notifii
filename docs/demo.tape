Output docs/demo.gif

Set FontSize 14
Set Width 1200
Set Height 600
Set Theme "Catppuccin Mocha"
Set Padding 20

Type "# Notifii — Production-grade notification platform"
Enter
Sleep 1s

Type "make run-demo"
Enter
Sleep 8s

Type "# Dashboard is now open at http://localhost:5173"
Enter
Sleep 2s

Type "# Let's send a notification via API"
Enter
Sleep 1s

Type@100ms 'curl -s -X POST http://localhost:8000/notifications -H "Content-Type: application/json" -d '"'"'{"to":"demo@test.com","subject":"Hello from Notifii","body":"Queue-backed delivery","channel":"email"}'"'"' | python3 -m json.tool'
Enter
Sleep 3s

Type "# ✓ Queued! Now let's simulate a provider failure"
Enter
Sleep 1s

Type@100ms 'curl -s -X POST http://localhost:8000/demo/send-test -H "Content-Type: application/json" -d '"'"'{"simulate_failure":true}'"'"' | python3 -m json.tool'
Enter
Sleep 3s

Type "# Message goes to Dead Letter Queue. Let's check it"
Enter
Sleep 1s

Type@100ms "curl -s http://localhost:8000/queue/dlq | python3 -m json.tool"
Enter
Sleep 3s

Type "# Now retry the DLQ message"
Enter
Sleep 1s

Type@100ms "curl -s -X POST http://localhost:8000/queue/dlq/retry | python3 -m json.tool"
Enter
Sleep 3s

Type "# ✓ Message delivered successfully after retry!"
Enter
Sleep 2s

Type "# Check metrics"
Enter
Type@100ms "curl -s http://localhost:8000/metrics"
Enter
Sleep 3s

Type ""
Enter
Type "# That's Notifii — event-driven, queue-backed, production-ready."
Enter
Sleep 3s
