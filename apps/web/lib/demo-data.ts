export const kpis=[
  ['Revenue','PKR 29.84M','+8.4%'],['Gross margin','27.6%','−2.1 pts'],['Inventory value','PKR 18.32M','+1.8%'],['Stockout risk','14 SKUs','+12.0%'],['Return rate','3.8%','+0.7 pts'],
];
export const attention=[
  ['Critical','Protect high-velocity demand','14 SKUs below policy cover; approval-controlled simulation available.'],
  ['High','Investigate margin erosion','Discounts and landed-cost variance affect Consumer Electronics.'],
  ['High','Repair delayed inventory freshness','Inventory snapshot is 14 hours behind its expected refresh schedule.'],
];
export const branches=[
  ['Lahore Branch','PKR 7.12M','30.4%','Healthy'],['Islamabad Branch','PKR 6.83M','24.1%','Watch'],['Karachi Branch','PKR 6.38M','29.7%','Healthy'],['Rawalpindi Branch','PKR 5.21M','28.2%','Healthy'],['Faisalabad Branch','PKR 4.30M','29.1%','Healthy'],
];
export const alerts=[
  ['Critical','Forecasted stockout in Islamabad','14 SKUs below seven days cover','Open'],['High','Inventory snapshot freshness delayed','Source is 14 hours behind SLA','Acknowledged'],['High','Consumer Electronics margin erosion','Discount intensity exceeds prior-period baseline','Open'],['High','Supplier delivery variance','NorthStar Imports open POs are late','Open'],
];
export const qualityIssues=[
  ['Critical','Supplier mapping missing for 16 products','products','16 records','Open'],['High','Inventory snapshot delayed by 14 hours','inventory_records','320 records','Acknowledged'],['Critical','Negative unit price in supplier file','sales_transactions','1 record','Open'],['Warning','Duplicate transaction import detected','sales_transactions','7 records','Open'],['Warning','Missing category mapping','products','9 records','Resolved'],
];
export const metricRows=[
  ['Revenue','revenue','Certified','sales_transactions','Analytics Engineering'],['Gross Profit','gross_profit','Certified','sales_transactions','Analytics Engineering'],['Gross Margin','gross_margin','Certified','sales_transactions · products','Finance'],['Stockout Risk','stockout_risk','Warning','inventory_records · suppliers','Supply Chain'],['Revenue Forecast','revenue_forecast','Certified','sales_transactions','Analytics Engineering'],
];
