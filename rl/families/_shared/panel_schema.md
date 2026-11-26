The data is at `/app/data/transactions.csv` with columns:

| column | meaning |
|---|---|
| `date` | day the transactions happened |
| `ct` | number of transactions the sensor reported that day |
| `amt` | total dollar value of those transactions |
| `ticker` | company (anonymised code) |
| `industry` | industry of the company |
| `source_id` | which data vendor ("sensor") reported the row; every company is covered by several sensors |

A day with no transactions has no row (there are no zero rows). The sensors are independent reads on the same
companies and can malfunction: under-report, double count, change their panel, go dark, or mislabel data.
