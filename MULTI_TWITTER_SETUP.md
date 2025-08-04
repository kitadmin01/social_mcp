# Multi-Account Twitter Integration

This document describes the new multi-account Twitter functionality that has been added to the social media workflow.

## Overview

The system now supports two Twitter accounts that can both post tweets and engage with other content simultaneously. This provides redundancy and increased reach for your social media automation.

## Configuration

### Environment Variables

The following environment variables have been added to support multiple Twitter accounts:

```env
# Primary Twitter Account
TWITTER_USERNAME=your_primary_username
TWITTER_PASSWORD=your_primary_password

# Secondary Twitter Account
TWITTER_USERNAME_2=your_secondary_username
TWITTER_PASSWORD_2=your_secondary_password
```

### Account Details

1. **Primary Account**: Your first Twitter account
2. **Secondary Account**: Your second Twitter account

## How It Works

### Posting Tweets

When the workflow generates tweets, both accounts will attempt to post the same content:

1. The primary account posts first
2. The secondary account posts second
3. A 2-second delay is added between posts to avoid rate limiting
4. The workflow considers it successful if at least one account posts successfully

### Engagement

Both accounts will engage with other tweets:

1. Each account searches for the same search terms
2. Each account likes up to 3 tweets (reduced from 5 to avoid over-engagement)
3. Engagement happens in parallel for both accounts

### Session Management

Each account maintains its own browser session:

- Primary account: `./playwright_session/primary/`
- Secondary account: `./playwright_session/secondary/`

This ensures that login sessions are preserved separately for each account.

## Testing

To test the multi-account functionality, run:

```bash
cd mcp_server/test
python test_multi_twitter.py
```

This will:
1. Test login for both accounts
2. Post a test tweet from each account
3. Test search and like functionality for each account
4. Verify that both accounts work independently

## Workflow Changes

### Updated Components

1. **MultiTwitterPlaywright Class**: New class in `mcp_server/tools/multi_twitter.py`
2. **Workflow Graph**: Updated to use both accounts for posting and engagement
3. **Client**: Updated to show status for both Twitter accounts

### Key Methods

- `post_tweet(text, account_name)`: Posts a tweet with the specified account
- `search_and_like_tweets(search_term, max_likes, account_name)`: Engages with tweets using the specified account
- `get_status()`: Returns status for both accounts

## Monitoring

The system now logs the status of both Twitter accounts:

```
Platform Status:
  Twitter (primary): Ready
  Twitter (secondary): Ready
  telegram: Ready
  bluesky: Ready
```

## Error Handling

- If one account fails to post, the other account will still attempt to post
- If one account fails to engage, the other account will still engage
- Each account has independent error tracking and retry mechanisms
- Session directories are separate, so issues with one account don't affect the other

## Benefits

1. **Redundancy**: If one account is temporarily blocked or has issues, the other can continue
2. **Increased Reach**: Two accounts posting the same content increases visibility
3. **Risk Distribution**: Engagement is spread across two accounts, reducing the risk of being flagged
4. **Independent Sessions**: Each account maintains its own login session and cookies

## Troubleshooting

### Common Issues

1. **Login Failures**: Check that both username/password combinations are correct
2. **Session Conflicts**: Clear the session directories if accounts get stuck
3. **Rate Limiting**: The system includes delays, but you may need to adjust timing

### Debugging

- Check the logs for account-specific messages
- Use the test script to verify each account independently
- Monitor the Google Sheets for posting results from both accounts

## Future Enhancements

Potential improvements for the multi-account system:

1. **Content Variation**: Generate slightly different content for each account
2. **Timing Optimization**: Stagger posting times to maximize reach
3. **Account-Specific Engagement**: Different engagement strategies per account
4. **Analytics**: Track performance metrics for each account separately 