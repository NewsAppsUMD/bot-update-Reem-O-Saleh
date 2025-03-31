# bot-update-Reem-O-Saleh

## FDA Recalls 

URL: https://open.fda.gov/apis/food/

## What I Did

I created a bot that sends notifications to slack when there is a new food product recall. The bot gets the most recent FDA food recall information using the API, formats it into a readable message with emojis, and sends alerts to the slack-bots Slack channel. JSON parsing is used to retrieve the recall data. 

## Future Directions

I might need to change the notification to be more of a structured sentence that states what product is being recalled, when, why, and by which company instead of the format the alerts are in now. The data is currently not being stored, the bot immediately sends out information, it may not be necessary to store the information, but it is something that could be implemented. 

Another thing that should be implemented is making the bot run on a schedule to fetch any new recall data that may be available. 

## Errors I Encountered 

I implemented error handling for API failures, which helped me figure out why errors were occurring. I did have errors that I was able to resolve like authentication errors that prevented the API from being integrated with Slack and sending out messages to Slack. 

## Lessons Learned (So Far)

- The data format is consistent with key fields like "reason_for_recall" "recalling_firm" and "product_description" present in each recall report 
- FDA API doesn't provide realtime webhook capabilities, so the notification system has to regularly check for updates
- Using environment variables is essential to keep authentication tokens out of the code repository
- Working with APIs requires robust error handling


