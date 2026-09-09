# Alpha Tester Requirements Questionnaire

This questionnaire is intended for alpha testers who are software developers. Its purpose is to collect requirements, usability feedback, quality concerns, and improvement priorities for the thesis project.

The questionnaire is based on the ISO/IEC 25010:2023 product quality model. ISO/IEC 25040:2024 may be cited as the evaluation-process inspiration, but unless the full standard is legally accessed and followed, describe the method as "informed by" or "adapted from" ISO/IEC 25040 rather than fully compliant with it.

## Suggested Consent Text

You are invited to evaluate the alpha version of the system. Your responses will be used for academic research and system improvement. No personal data beyond the profile questions below will be reported in a way that identifies you. Participation is voluntary, and you may skip any item that does not apply.

## Response Scale

For rating items, use this 4-point Likert scale:

1. Strongly disagree
2. Disagree
3. Agree
4. Strongly agree

Add an `N/A` option for questions that do not apply to the tester's assigned task or access level.

## Section A: Respondent Profile

1. Current role or specialization:
   - Frontend developer
   - Backend developer
   - Full-stack developer
   - QA/test engineer
   - DevOps/cloud engineer
   - Student developer
   - Other: ________

2. Years of software development experience:
   - Less than 1 year
   - 1 to 2 years
   - 3 to 5 years
   - More than 5 years

3. Technologies you commonly work with:
   - Web frontend
   - Backend/API development
   - Database design
   - Cloud/deployment
   - Security
   - UI/UX testing
   - Automated testing
   - Other: ________

4. Have you previously participated in alpha or beta testing?
   - Yes
   - No

5. What device did you use for testing?
   - Desktop or laptop
   - Tablet
   - Mobile phone

6. What browser did you use?
   - Chrome
   - Edge
   - Firefox
   - Safari
   - Other: ________

## Section B: Evaluation Context

1. Which user role did you test?
   - Public visitor
   - Employee/user
   - Validator/reviewer
   - Administrator
   - Other: ________

2. Which modules or workflows did you test? Select all that apply.
   - Login/account access
   - Public website pages
   - Project submission
   - Project review or validation
   - Content management
   - Reports or dashboards
   - Search/filtering
   - File upload/download
   - Notifications
   - Other: ________

3. Were you able to complete the assigned testing tasks?
   - Yes, all tasks
   - Yes, most tasks
   - Some tasks only
   - No

4. If you were unable to complete any task, what blocked you?

   Response: ________

## Section C: Functional Requirements

Rate each statement.

| ID | Item | Rating |
| --- | --- | --- |
| FR1 | The system provides the core features needed for its intended users. | 1 2 3 4 5 N/A |
| FR2 | The available features match the workflow expected for my assigned user role. | 1 2 3 4 5 N/A |
| FR3 | The system produces correct results, outputs, or records based on the actions I performed. | 1 2 3 4 5 N/A |
| FR4 | Required inputs, buttons, and actions are available when they are needed. | 1 2 3 4 5 N/A |
| FR5 | The system prevents or flags incomplete, invalid, or inconsistent data entry. | 1 2 3 4 5 N/A |

Open-ended:

1. What required feature or workflow is missing?
2. What existing feature should be changed or simplified?
3. What feature should be prioritized before beta testing or deployment?

## Section D: ISO/IEC 25010:2023 Product Quality Items

### Functional Suitability

| ID | Item | Rating |
| --- | --- | --- |
| FS1 | The system includes the functions needed to complete the tested workflow. | 1 2 3 4 5 N/A |
| FS2 | The system responses and stored data appear accurate. | 1 2 3 4 5 N/A |
| FS3 | Each feature supports the user's task without unnecessary steps. | 1 2 3 4 5 N/A |

### Performance Efficiency

| ID | Item | Rating |
| --- | --- | --- |
| PE1 | Pages, forms, and actions load within an acceptable time. | 1 2 3 4 5 N/A |
| PE2 | The system remains responsive during common tasks such as searching, submitting, reviewing, or uploading. | 1 2 3 4 5 N/A |
| PE3 | The system appears capable of handling expected data volume and user activity for alpha-stage testing. | 1 2 3 4 5 N/A |

### Compatibility

| ID | Item | Rating |
| --- | --- | --- |
| CO1 | The system works correctly in the browser, device, and environment I used. | 1 2 3 4 5 N/A |
| CO2 | The system can exchange or display data in formats expected by users, such as forms, reports, files, or records. | 1 2 3 4 5 N/A |
| CO3 | The system does not interfere with normal browser behavior, file handling, or user session behavior. | 1 2 3 4 5 N/A |

### Interaction Capability

| ID | Item | Rating |
| --- | --- | --- |
| IC1 | I could understand what each page or screen was for. | 1 2 3 4 5 N/A |
| IC2 | I could learn how to use the system with minimal guidance. | 1 2 3 4 5 N/A |
| IC3 | Controls, labels, messages, and navigation were clear. | 1 2 3 4 5 N/A |
| IC4 | The system helped me avoid user errors or recover from them. | 1 2 3 4 5 N/A |
| IC5 | The interface was accessible and readable for the device I used. | 1 2 3 4 5 N/A |

### Reliability

| ID | Item | Rating |
| --- | --- | --- |
| RE1 | The system completed actions without crashes, unexpected errors, or broken pages. | 1 2 3 4 5 N/A |
| RE2 | The system remained available throughout the testing session. | 1 2 3 4 5 N/A |
| RE3 | The system handled mistakes, interruptions, or invalid actions without losing important data. | 1 2 3 4 5 N/A |
| RE4 | When an error occurred, the system provided enough information to continue or report the issue. | 1 2 3 4 5 N/A |

### Security

| ID | Item | Rating |
| --- | --- | --- |
| SE1 | The system restricts access to features and data according to the user's role. | 1 2 3 4 5 N/A |
| SE2 | Sensitive information is not exposed unnecessarily on screens, URLs, responses, or downloadable files. | 1 2 3 4 5 N/A |
| SE3 | User actions that create, update, approve, reject, or publish records appear traceable. | 1 2 3 4 5 N/A |
| SE4 | Authentication and session behavior appear appropriate for the system's intended use. | 1 2 3 4 5 N/A |
| SE5 | The system appears resistant to common misuse, such as unauthorized access, invalid input, or direct URL access. | 1 2 3 4 5 N/A |

### Maintainability

These items are best answered by testers who can inspect the codebase, API behavior, or technical structure. Use `N/A` if the tester only used the interface.

| ID | Item | Rating |
| --- | --- | --- |
| MA1 | The system structure appears modular and organized. | 1 2 3 4 5 N/A |
| MA2 | Components, services, or modules appear reusable where appropriate. | 1 2 3 4 5 N/A |
| MA3 | The code, API behavior, or project structure would be understandable to another developer. | 1 2 3 4 5 N/A |
| MA4 | The system appears easy to modify when requirements change. | 1 2 3 4 5 N/A |
| MA5 | The system appears testable through manual tests, automated tests, or API-level checks. | 1 2 3 4 5 N/A |

### Flexibility

| ID | Item | Rating |
| --- | --- | --- |
| FL1 | The system can be adapted to new user roles, fields, pages, or workflows without major redesign. | 1 2 3 4 5 N/A |
| FL2 | The system appears scalable enough for expected future users, records, files, or transactions. | 1 2 3 4 5 N/A |
| FL3 | The system appears deployable or installable in the intended environment. | 1 2 3 4 5 N/A |
| FL4 | The system could replace or integrate with existing manual or digital processes with minimal disruption. | 1 2 3 4 5 N/A |

### Safety

For information systems, safety can include preventing harmful operational outcomes such as accidental publication, data loss, wrong approval decisions, or misleading records.

| ID | Item | Rating |
| --- | --- | --- |
| SA1 | The system reduces the risk of harmful user actions, such as accidental deletion, wrong approval, or unintended publication. | 1 2 3 4 5 N/A |
| SA2 | The system provides warnings or confirmations before critical actions. | 1 2 3 4 5 N/A |
| SA3 | The system helps identify risks, inconsistencies, or potentially incorrect records before they affect users. | 1 2 3 4 5 N/A |
| SA4 | If a failure occurs, the system minimizes harm by preserving data or preventing unsafe continuation. | 1 2 3 4 5 N/A |
| SA5 | The system can be used alongside existing organizational processes without creating new operational risks. | 1 2 3 4 5 N/A |

## Section E: Priority and Requirements Elicitation

1. Rank the top five quality characteristics that should be prioritized before beta testing:
   - Functional suitability
   - Performance efficiency
   - Compatibility
   - Interaction capability
   - Reliability
   - Security
   - Maintainability
   - Flexibility
   - Safety

2. Which issue has the highest impact on system acceptance?

   Response: ________

3. Which issue is easiest to fix but would significantly improve the system?

   Response: ________

4. What additional requirement should be added?

   Response: ________

5. What requirement should be removed, reduced, or postponed?

   Response: ________

6. What test case or scenario should the development team add?

   Response: ________

7. Overall, is the alpha version ready to proceed to beta testing after revisions?
   - Yes
   - Yes, with minor revisions
   - No, major revisions are needed
   - Not sure

8. Explain your answer.

   Response: ________

## Optional Developer Defect Report

Use this section for each defect or technical issue observed.

| Field | Response |
| --- | --- |
| Issue title | |
| Module/page | |
| User role | |
| Steps to reproduce | |
| Expected result | |
| Actual result | |
| Severity | Low / Medium / High / Critical |
| Suggested fix | |
| Screenshot or evidence | |

## Suggested Evaluation Process

This lightweight process is adapted from the public description of ISO/IEC 25040:2024 as a quality evaluation framework.

1. Establish evaluation purpose

   Define that the alpha evaluation aims to identify missing requirements, quality risks, and readiness for beta testing.

2. Define evaluation scope

   List the modules, roles, devices, browsers, and workflows included in alpha testing.

3. Specify evaluation criteria

   Use the ISO/IEC 25010:2023 quality characteristics as criteria. Define passing targets, such as:

   - Mean rating of at least 4.00 per characteristic
   - No unresolved critical defects
   - High-severity defects must have documented fixes or mitigation plans
   - At least 80 percent task completion rate among alpha testers

4. Design the evaluation

   Prepare test accounts, test data, task scenarios, questionnaire forms, defect report templates, and consent text.

5. Execute the evaluation

   Ask each tester to complete assigned tasks, answer the questionnaire, and submit defect reports.

6. Analyze results

   Compute the mean or median score per quality characteristic. Review open-ended answers using themes such as missing feature, confusing workflow, performance issue, security concern, and deployment concern.

7. Conclude and report

   Summarize strengths, weaknesses, recommended requirements, accepted revisions, rejected revisions, and readiness for the next testing phase.

## Suggested Scoring Table

| Quality characteristic | Related item IDs | Mean score | Interpretation |
| --- | --- | --- | --- |
| Functional suitability | FS1 to FS3, FR1 to FR5 | | |
| Performance efficiency | PE1 to PE3 | | |
| Compatibility | CO1 to CO3 | | |
| Interaction capability | IC1 to IC5 | | |
| Reliability | RE1 to RE4 | | |
| Security | SE1 to SE5 | | |
| Maintainability | MA1 to MA5 | | |
| Flexibility | FL1 to FL4 | | |
| Safety | SA1 to SA5 | | |

Suggested interpretation:

| Mean range | Interpretation |
| --- | --- |
| 4.21 to 5.00 | Very satisfactory |
| 3.41 to 4.20 | Satisfactory |
| 2.61 to 3.40 | Needs improvement |
| 1.81 to 2.60 | Poor |
| 1.00 to 1.80 | Critical concern |

## References

- ISO. ISO/IEC 25010:2023, Systems and software engineering - Systems and software Quality Requirements and Evaluation (SQuaRE) - Product quality model. https://www.iso.org/standard/78176.html
- ISO. ISO/IEC 25040:2024, Systems and software engineering - Systems and software Quality Requirements and Evaluation (SQuaRE) - Quality evaluation framework. https://www.iso.org/standard/83467.html
- IEC Webstore. ISO/IEC 25040:2024 publication details. https://webstore.iec.ch/en/publication/100734
