
Anomaly Detection Exercise
Overview
Our investment process often starts with datasets that include a fair bit of signal but also significant noise. Attached is a very small (and partially simplified/derived) subset of data that counts the number of transactions and the amount spent per day at various companies/company segments as reported by four anonymized data sources. You can think of these data sources abstracted as ‘sensors’ that provide a timely read on underlying company trends, which may malfunction and provide poor reads at times.
We would like you to take this data and build a model that outputs a confidence score or probability for each datapoint that indicates where the data can be trusted or not trusted. Specifically, we are looking to cleanse the data of two types of potential issues:
Anomalous values: An individual datapoint can often be too low if a sensor doesn’t properly transmit the data, or too high for a variety of reasons (double counting/contamination/etc.).
Sudden level shifts across time: if a sensor changes the way it behaves, the read may be higher or lower persistently in perpetuity or for a period of time.
At this stage, there is no ‘ground truth’ or training data. But you can use past history or some notion of what is going on across timeseries to get a sense for what is normal.
Importantly, the model should not use foresight (i.e. data with future dates) to inform what is likely anomalous in the past. As such, the model should get better at divining confidence over time (though you may not be able to quantify, which is fine).
Data Description
Attached is an Excel file with two data-frames that contain the same data in two formats (one is pivoted for your convenience, but feel free not to use if you are just going to import flat tab).
Looking at the ‘flat’ tab:
Date is the day that a transaction occurred
Ct is the number of transactions the sensor reported
Amt is the dollar value of those transactions all added up
Ticker is either a company or in the case where an underline is present, a company segment (i.e., AAL is American Airlines while JWN_RACK is Nordstrom Rack)
Industry is self-explanatory. Note that we have only provided two here out of many that exist.
Source_id is a unique ID for each sensor. Note that there are only four provided here.
Guidance
Spend some time looking at the data before beginning. You will be able to see several instances of large data spikes and level shifts with the naked eye. Those are the types of items that we want to identify at scale (i.e. imagine you had to do this across hundreds more sensors and companies; the bar for the model is to identify those obviously wrong datapoints in an automated fashion).
Use whatever analytical tools and methods you are comfortable with. Learning a new language or technique is certainly not required. We tend to work in python, but use whatever is best for you.
Feel free to use any open-source packages that are helpful (but do let us know which you’ve chosen if any and why), or none at all.
Spend whatever time you think is required to get to a MVP output. This probably looks like a day, maybe two. We don’t expect you to ‘solve’ the problem fully (and to some extent the problem can’t be fully solved). We just want to see how you would approach the problem and what sort of scrappy results you can generate, while being cognizant of your time. Please keep track of your time so we know what you invested.
Simple is fine. Don’t feel the need to dazzle us with complexity if it isn’t immediately helpful.
Feel free to throw out any ‘junk’ data if it helps you (for instance, the leading portion of a sensor if there are very few transactions, but please do so programmatically within the model (so that your methodology could theoretically scale).
Necessary output is a confidence score for each datapoint. Better would be some notion of whether you believe a datapoint represents a point-anomaly or a level-shift. If you would like to produce a ‘clean’ version of each timeseries (i.e. removing or replacing an anomalous values, or adjusting a timeseries to remove the impact of a level-shift) that would be interesting for inspection, but is not required. Any means of clearly visualizing your output would also be helpful but is not required.
Ultimately, please deliver your output above, plus the code you used to generate the output in a reproduceable / interpretable format (this could be a notebook or just commented code). Presentation of the output need not be anything formal, but plan to chat through briefly afterwards to discuss your approach, what went well / not well, and what you would do with more time / etc. should complete the exercise.
Ask whatever questions you’d like, but note that we are purposely keeping the means of attack open-ended to see how you think about things.
