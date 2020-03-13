

## The data format

The data format used for generating the status page is a `yaml` file with the following sections:
```yaml
# The products shown in the overview columns
products:
  - Network
  - Some product

# A list of current problems/info
current:
  - title: Item title
    status: outage
    start: 2020-03-13 09:30 UTC
    products: # Products should match the products defined above
      - Some product
    body: >
      <p>Html enabled body, only shown in when on the current events</p>
    updates: # A list of updates
      - title: Update
        time: 2020-03-12 10:00 UTC
        body: Keep updates simple
      - title: Investigating
        time: 2020-03-12 09:30 UTC
        body: Some descriptive info

# A list of planned upcomming work
# same format as the other events
planned: []

# A list of past incidents
past:
  - title: Item title
    status: degraded
    products:
      - Some product
    updates:
      - title: Resolved:
        time: 2020-03-12 14:00 UTC
        body: The issue has been resolved.
      - title: Monitoring
        time: 2020-03-12 13:00 UTC
        body: The issue has now been mitigated, we continue to monitor the situation.
      - title: Investigating
        time 2020-03-12 10:30 UTC
        body: We are currently seeing problems with the plonk of the Some service.
    # the body will not be shown
    body: >
      <p>this body will currently not be shown, but can be kept for future use</p>
```

Currently the following status are supported:

- operational - green
- degraded - orange
- outage - red
- maintenance - blue

If you put anything else it will end up being gray and black.

The products status grid gets updated depending on `products` in the current list. Currently in reverse order, so oldest status wins.
