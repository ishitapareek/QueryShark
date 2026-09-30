# QueryShark

QueryShark is a MySQL query performance monitoring tool. The system monitors SQL queries executed against a database, retrieves execution metrics using the MySQL Performance Schema, detects slow queries, records query metrics, and will provide dashboard and reporting capabilities.



## Project Structure

```text
QueryShark/
│
├── app/
│   └── main.py              # Main application 
│
├── queryshark/
│   └── demo.py              # Query capturing middleware 
│
├── database/
│   └── database.sql         # Schema setup 
│
├── ui/
│   ├── index.html           # Performance monitoring dashboard
│   ├── styles.css           
│   ├── app.js               # Frontend controller & filtering
│   └── README.md            # UI documentation
│
├── tests/
│   └── test.py              # Test scripts
│
├── docs/
│   └── architecture.md      # Architecture and documentation
│
├── requirements.txt         # Project dependencies
├── README.md                # Project documentation
└── .gitignore               # Git ignore rules
```

## Setup & Dependencies
Install the required packages:
```bash
pip install -r requirements.txt
```