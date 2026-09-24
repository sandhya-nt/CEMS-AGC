# 📋 ACEMS AGC — Safe Incremental Implementation Plan

> **Purpose**: A phased, low-risk roadmap for evolving the CEMS AGC platform.
> Each module is independent, testable in isolation, and builds on completed prior work.
> **No modifications are applied to source code in this document.**

---

## 🎯 18 Prioritized Modules

| # | Module | Priority | Category | Est. Effort | Status |
|---|--------|----------|----------|-------------|--------|
| 1 | **Authentication & Routing** | 🔴 HIGH | Auth | 1 day | ⚪ Planned |
| 2 | **Registration Wizard** | 🔴 HIGH | Auth | 1 day | ⚪ Planned |
| 3 | **Landing Page & Categories** | 🔴 HIGH | UI | 1 day | ⚪ Planned |
| 4 | **Student Dashboard** | 🔴 HIGH | Core | 1 day | ⚪ Planned |
| 5 | **Organizer Dashboard** | 🔴 HIGH | Core | 1 day | ⚪ Planned |
| 6 | **Event Creation Flow** | 🔴 HIGH | Core | 2 days | ⚪ Planned |
| 7 | **Event Registration & Tickets** | 🔴 HIGH | Core | 2 days | ⚪ Planned |
| 8 | **Attendance & Check-in** | 🔴 HIGH | Core | 2 days | ⚪ Planned |
| 9 | **Notification System** | 🟡 MEDIUM | Core | 1 day | ⚪ Planned |
| 10 | **Reports & Analytics** | 🟡 MEDIUM | Core | 2 days | ⚪ Planned |
| 11 | **Payment Integration** | 🟡 MEDIUM | Core | 2 days | ⚪ Planned |
| 12 | **Certificate Management** | 🟡 MEDIUM | Core | 1 day | ⚪ Planned |
| 13 | **Feedback & Ratings** | 🟡 MEDIUM | Engagement | 1 day | ⚪ Planned |
| 14 | **Volunteer Management** | 🟢 STANDARD | Ops | 1 day | ⚪ Planned |
| 15 | **Faculty Event Ops** | 🟢 STANDARD | Faculty | 1-2 days | ⚪ Planned |
| 16 | **Admin Panel** | 🟢 STANDARD | Admin | 1 day | ⚪ Planned |
| 17 | **Kiosk Mode** | 🟢 STANDARD | Ops | 1 day | ⚪ Planned |
| 18 | **Search & Discover** | 🟢 STANDARD | UX | 1 day | ⚪ Planned |

---

## 📁 Current State Reference

### Already Implemented (from codebase analysis)

The codebase already contains substantial functionality. Here's what exists today:

#### ✅ **Fully Implemented**
- **Authentication Layer**: Single centralized auth (Flask-Login + Werkzeug), `@role_required` decorator, `@login_required`, CSRF protection, rate limiting
- **Registration System**: Multi-step wizard with validation endpoint, 3 role-specific registration forms (student/faculty/organizer), email verification workflow
- **Dashboard Routing**: Role-aware redirect chain (`/dashboard` → role-specific dashboard), 5 dashboard views (student/teacher/organizer/admin/volunteer)
- **Event Management**: Full CRUD (create, edit, cancel, reschedule), approval workflow, 35+ seeded events across 6 categories
- **Registration & Tickets**: Capacity checking, deadline validation, duplicate prevention, QR code ticket generation, digital tickets
- **Attendance System**: QR code scanning, kiosk check-in, attendance tracking with timestamps
- **Notifications**: Robust `Notification` model with categories, priorities, actions, read status; `MultiChannelNotification`, `CampusAnnouncement` models
- **Reports & Analytics**: Revenue analytics, attendance charts, participant demographics, event performance metrics, CSV/PDF export
- **Certificate System**: `DigitalCertificate` model, generation via ReportLab, verification page, `EventCredit` model
- **Payment Handling**: Demo/mock payment integration with status tracking
- **Feedback System**: Form builder, responses, sentiment analysis models (`FeedbackSentiment`), `Feedback` model
- **Volunteer Management**: Roles, applications, assignments, performance tracking (`VolunteerPerformance`)
- **Guest Management**: `VIPGuestManagement` model with check-in tracking
- **Task Management**: `EventTask` model with status/priority tracking
- **Incident Reporting**: `EventEmergency` model with severity levels
- **Resource Management**: `Resource`, `EquipmentInventory` models with booking system
- **Search**: Event search with category and status filtering

#### 🟡 **Partially Implemented**
- **Faculty Event Operations** (see FACULTY_ROADMAP.md):
  - Winner & Result Management — model fields exist, no entry UI
  - Incident Reporting — model exists, no UI
  - Guest Management — model exists, no UI
  - Equipment Requests — models exist, no faculty workflow
  - Task Management — model exists, no UI
  - Faculty Calendar — template exists, no calendar view

#### 🟡 **UI/UX Enhancements Needed**
- `teacher/dashboard.html` has hardcoded sidebar (should use base.html inheritance)
- Landing page needs role-specific login links
- 403 error handler needs friendly page

---

## 🏗️ Phased Implementation Plan

### Phase 1 — Authentication Foundation (Days 1-2)
**Goal**: Ensure robust, role-aware authentication with clean routing

#### Module 1: Authentication & Routing (1 day)
- **Scope**: Enhance `/login` POST handler with role-aware redirect
- **Changes**:
  - Modify `/login` POST to redirect based on `current_user.role`:
    - `student` → `/student/dashboard`
    - `teacher` → `/teacher/dashboard`
    - `organizer` → `/organizer/dashboard`
    - `admin` → `/admin/dashboard`
  - Enhance `/api/login` JSON response with role-specific redirect URL
- **Testing**: Verify login redirects correctly for each role, verify 403 on wrong-dashboard access
- **Risk**: Low — only changes redirect logic, no auth logic change

#### Module 2: Registration Wizard (1 day)
- **Scope**: Verify and enhance multi-step registration
- **Changes**:
  - Review existing `/api/register/validate-step` endpoint
  - Ensure role mapping works (`faculty` → `teacher` internal role)
  - Add client-side validation feedback if missing
- **Testing**: Register as each role type, verify email verification workflow
- **Risk**: Low — mostly verification of existing functionality

### Phase 2 — Core User Experience (Days 3-4)
**Goal**: Polished landing page and dashboards

#### Module 3: Landing Page & Categories (1 day)
- **Scope**: Finalize landing page with clickable categories and role login links
- **Changes**:
  - Add role-specific login links to `templates/landing.html`:
    - `/login/student`, `/login/faculty`, `/login/organizer`
  - Ensure all 6 category cards link to filtered event lists
  - Verify responsive design for mobile
- **Testing**: Click each category, verify filtering works; click each role login link
- **Risk**: Low — only template changes

#### Module 4: Student Dashboard (1 day)
- **Scope**: Complete student-side functionality
- **Changes**:
  - Verify statistics cards update in real-time
  - Ensure notifications badge shows unread count
  - Confirm upcoming events grid displays correctly
- **Testing**: Student registers for event, verify dashboard updates
- **Risk**: Low — verification and minor enhancements

#### Module 5: Organizer Dashboard (1 day)
- **Scope**: Complete organizer-side functionality
- **Changes**:
  - Verify event management table works (edit, delete, view registrations)
  - Confirm statistics cards (Total Events, Registrations, Attendees, Revenue)
  - Ensure quick-action buttons work
- **Testing**: Organizer creates event, verifies dashboard reflects it
- **Risk**: Low — verification and minor enhancements

### Phase 3 — Event Lifecycle (Days 5-8)
**Goal**: Full event creation, registration, and attendance flow

#### Module 6: Event Creation Flow (2 days)
- **Scope**: Complete event creation with all fields
- **Changes**:
  - Review `templates/organizer/create_event.html` for completeness
  - Verify category selection, date/time, venue, capacity, fee handling
  - Ensure auto-save drafts feature works
  - Add form validation feedback
- **Testing**: Create event with all fields, verify in database, check event detail page
- **Risk**: Medium — touches form submission and model persistence

#### Module 7: Event Registration & Tickets (2 days)
- **Scope**: End-to-end registration to ticket receipt
- **Changes**:
  - Verify capacity checking logic
  - Confirm deadline validation
  - Ensure QR code generation works
  - Test payment flow (mock) for paid events
  - Verify confirmation emails send
- **Testing**: Register for free and paid events, verify ticket generation
- **Risk**: Medium — touches registration, payment, and ticket services

#### Module 8: Attendance & Check-in (2 days)
- **Scope**: Complete attendance tracking workflow
- **Changes**:
  - Review `templates/organizer/checkin.html` and `qr_scanner.html`
  - Verify QR scanning works for check-in
  - Ensure attendance timestamps record correctly
  - Confirm real-time attendance count updates
- **Testing**: Scan QR code, verify attendance recorded, check count updates
- **Risk**: Medium — touches attendance service and check-in flow

### Phase 4 — Platform Services (Days 9-12)
**Goal**: Notifications, analytics, payments, certificates

#### Module 9: Notification System (1 day)
- **Scope**: Complete notification delivery and management
- **Changes**:
  - Verify `Notification` model categories work
  - Ensure notifications display in user dashboards
  - Test mark-as-read functionality
  - Confirm notification categories: event_approval, registration_confirmation, payment_status, etc.
- **Testing**: Trigger event registration, verify notification appears
- **Risk**: Low — verification of existing notification system

#### Module 10: Reports & Analytics (2 days)
- **Scope**: Complete analytics and reporting capabilities
- **Changes**:
  - Review `templates/organizer/reports.html` and `templates/admin/reports.html`
  - Verify charts render (using `static/js/charts.js`)
  - Confirm CSV/PDF export works
  - Ensure date range filters function
- **Testing**: Generate reports for event, verify export files
- **Risk**: Medium — touches reporting queries and export logic

#### Module 11: Payment Integration (2 days)
- **Scope**: Complete payment flow for paid events
- **Changes**:
  - Replace demo/mock payment with structured flow
  - Verify payment status tracking (paid, pending, failed)
  - Ensure payment status shows in registrations table
  - Add receipt generation (if applicable)
- **Testing**: Register for paid event, simulate payment, verify status
- **Risk**: Medium — touches financial data, ensure audit trail

#### Module 12: Certificate Management (1 day)
- **Scope**: Complete certificate generation and verification
- **Changes**:
  - Review `templates/verify_certificate.html`
  - Verify certificate generation on event completion
  - Ensure verification page works (enter code → see certificate)
  - Confirm `DigitalCertificate` model fields populate correctly
- **Testing**: Complete event attendance, generate certificate, verify via code
- **Risk**: Low — verification of existing certificate system

### Phase 5 — Engagement Features (Days 13-14)
**Goal**: Feedback, volunteers, and community engagement

#### Module 13: Feedback & Ratings (1 day)
- **Scope**: Complete feedback collection and analysis
- **Changes**:
  - Review feedback form builder (`templates/organizer/feedback_form_builder.html`)
  - Verify feedback responses are collected
  - Check sentiment analysis integration (`FeedbackSentiment` model)
  - Ensure student feedback forms render
- **Testing**: Submit feedback for event, verify sentiment analysis runs
- **Risk**: Low — verification of existing feedback system

#### Module 14: Volunteer Management (1 day)
- **Scope**: Complete volunteer coordination
- **Changes**:
  - Review `templates/organizer/volunteer_management.html`
  - Verify volunteer application/approval workflow
  - Confirm assignment tracking (`VolunteerAssignment` model)
  - Check performance feedback collection
- **Testing**: Apply as volunteer, get assigned, verify performance tracking
- **Risk**: Low — verification of existing volunteer system

### Phase 6 — Faculty Operations (Days 15-16)
**Goal**: Faculty-specific event management tools

#### Module 15: Faculty Event Ops (1-2 days)
- **Scope**: Implement faculty event management (from FACULTY_ROADMAP.md Phase 2)
- **Changes** (implement items still pending):
  - Winner & Result Management — create entry form, verification workflow
  - Guest Management — create registration UI, check-in tracking
  - Equipment Requests — faculty-facing request workflow
  - Task Management — task board UI
  - Incident Reporting — incident report UI
- **Testing**: Faculty completes event, enters winners, manages guests
- **Risk**: High — significant new features, requires careful model/route mapping

### Phase 7 — Administrative & Specialized Tools (Days 17-18)
**Goal**: Admin panel completion, kiosk mode, search

#### Module 16: Admin Panel (1 day)
- **Scope**: Complete admin functionality
- **Changes**:
  - Review all admin templates (`templates/admin/`)
  - Verify user management (block/unblock)
  - Confirm event approval workflow
  - Test audit log functionality (`templates/admin/audit_logs.html`)
- **Testing**: Admin approves pending event, verifies user blocking
- **Risk**: Low — verification of existing admin system

#### Module 17: Kiosk Mode (1 day)
- **Scope**: Complete self-service kiosk for event check-in
- **Changes**:
  - Review `templates/kiosk/kiosk.html` and `static/js/kiosk.js`
  - Verify kiosk mode works on mobile/tablet
  - Ensure no login required (public-facing)
  - Confirm QR/code entry works for check-in
- **Testing**: Access kiosk URL on device, check in via code
- **Risk**: Low — verification of existing kiosk system

#### Module 18: Search & Discover (1 day)
- **Scope**: Enhanced search across events, users, and registrations
- **Changes**:
  - Review `templates/search.html`
  - Verify search returns relevant results
  - Add filters (by category, date, status, role)
  - Ensure search works across events and notices
- **Testing**: Search for events by keyword, category, date
- **Risk**: Low — enhancement of existing search

---

## 🛡️ Safety Principles

1. **Incremental**: Each module delivers a small, testable unit
2. **Non-blocking**: Modules can be developed in parallel where independent
3. **Reversible**: All changes are git-committed, allowing rollback
4. **Test-first**: Write or verify tests before each module
5. **No big refactors**: Extend existing patterns, don't rewrite working code

## 🧪 Testing Strategy

- **Unit tests**: Run existing test suite (`run_tests.py`) after each module
- **Integration tests**: Use existing test files (`test_event_workflow*.py`, `test_student_reg.py`, etc.)
- **Manual verification**: Follow PROFESSIONAL_IMPLEMENTATION.md usage guide for each feature

## 📊 Effort Summary

| Phase | Modules | Est. Days | Priority |
|-------|---------|-----------|----------|
| Phase 1 — Auth Foundation | 1, 2 | 2 | 🔴 HIGH |
| Phase 2 — Core UX | 3, 4, 5 | 3 | 🔴 HIGH |
| Phase 3 — Event Lifecycle | 6, 7, 8 | 6 | 🔴 HIGH |
| Phase 4 — Platform Services | 9, 10, 11, 12 | 6 | 🟡 MEDIUM |
| Phase 5 — Engagement | 13, 14 | 2 | 🟡 MEDIUM |
| Phase 6 — Faculty Ops | 15 | 2 | 🟢 STANDARD |
| Phase 7 — Admin & Tools | 16, 17, 18 | 3 | 🟢 STANDARD |

**Total**: 18 modules | ~24 developer-days | 5 phases

---

*This plan is a living document. Each module is independent and can be confirmed individually before implementation begins.*
