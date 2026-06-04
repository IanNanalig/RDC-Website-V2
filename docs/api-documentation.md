# API Documentation Notes

The Django API is served under `/api/` from `backend/projects/urls.py`.

Important API groups:

- Authentication and password setup/reset
- Employee project submissions
- Validator review and progress revisions
- Admin user/activity/window controls
- Public projects dashboard endpoints
- Public chatbot endpoints

Public endpoints must not require JWT headers and must avoid exposing raw workflow data or private `profile_data`.
