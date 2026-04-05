# damu-exchange - Blood Donation Platform

## Product Vision
A platform connecting blood donors with recipients - people can volunteer to donate and those needing transfusions can request blood.

## Users

### Donors
- Register personal info (name, phone, blood type, location)
- Set availability status
- View nearby requests
- Get notified when匹配的 requests
- Track donation history

### Recipients/Requesters
- Create blood request (patient info, blood type needed, hospital, urgency)
- View matching donors
- Update request status (fulfilled/cancelled)
- Rate donor experience

### Admins
- Verify donors/recipients
- Track all donations
- Analytics dashboard

## MVP Features

### 1. Donor Registration
- Phone number
- Full name
- Blood type (A+, A-, B+, B-, AB+, AB-, O+, O-)
- Location (county/city)
- Health clearance status
- Availability toggle

### 2. Blood Request
- Patient name
- Blood type needed
- Hospital/health facility
- Units needed
- Urgency level (routine/urgent/critical)
- Doctor contact
- Status (pending/fulfilled/expired)

### 3. Matching
- Filter by blood type
- Filter by location
- Push notifications to matching donors

### 4. Status Tracking
- Request created → Donors notified → Donor responds → Donation made → Request fulfilled

## Tech Stack
- Frontend: React Native (Expo) or Simple HTML/Telegram bot
- Backend: Supabase or simple API
- Notifications: Push via Telegram or SMS

## Monetization
- Free initially (social good)
- Premium for hospitals/clinics later
- Corporate blood drive packages

## Name Ideas
- DamuExchange (Swahili: damu = blood)
- BloodBridge
- LifeDrop
- AfyaYetu (OurHealth)
- DamuConnect

## Next Steps
1. Create project structure
2. Choose platform (Telegram bot or web app)
3. Build donor registration flow
4. Build request flow
5. Test with small group

## Deployment (Render.com)

### Quick Deploy
```bash
# Push to GitHub, then:
render.com → New Web Service → Connect GitHub repo
```

### Environment Variables
- `TELEGRAM_BOT_TOKEN`: Your bot token (already in .env)