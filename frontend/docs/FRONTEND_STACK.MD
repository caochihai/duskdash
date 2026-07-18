# Frontend Technology Stack

## Technology Responsibilities

* **Vite:** Project scaffolding, development server, and production build.

* **React:** Components, pages, layouts, and local UI state management.

* **TypeScript:** Primary language for frontend source code. Used to define component props, routes, API responses, and shared types.

* **React Router:** Routing, navigation, and breadcrumbs. All routes should be declared centrally in `src/app/routes.tsx`.

* **Ant Design:** Standard application UI, including Layout, Sidebar, Menu, Table, Form, Input, Select, Button, Card, Tabs, Drawer, Modal, Upload, Steps, Timeline, Tag, Alert, Skeleton, Empty, Result, and Notification.

* **Ant Design Icons:** The single icon source across the application.

* **Ant Design X:** AI interaction components, including Sender, Bubble, Attachments, FileCard, Sources, Actions, Conversations, ThoughtChain, and AI processing states. It must not replace standard application UI.

* **Ant Design Charts:** Charts and data visualizations. Data and configuration must be provided through component props.

* **TanStack Query:** Server-state management, including fetching, caching, loading, error handling, retries, and invalidation. It must not be used for local UI state such as opening modals or collapsing the sidebar.

* **Axios:** The shared HTTP client. Create one Axios instance in `src/services/apiClient.ts` and read the base URL from `VITE_API_BASE_URL`. Components must not call Axios directly; requests should be made through services or query hooks.

* **Motion for React:** Micro-interactions and special UI transitions, such as opening the AI panel, changing layouts, or animating element entry and exit. Simple hover and focus effects should use CSS transitions.

* **Ant Design ConfigProvider:** Centralized theme configuration under `src/theme/`.

* **CSS Modules:** Custom styling when Ant Design props and theme tokens are insufficient. Do not use Tailwind CSS, Styled Components, or another UI kit.

## Installation

If the repository is empty:

```bash
npm create vite@latest . -- --template react-ts
```

Install the required dependencies:

```bash
npm install antd@^6 @ant-design/icons@^6
npm install @ant-design/x@^2 @ant-design/charts@^2
npm install react-router-dom@^7
npm install @tanstack/react-query@^5 axios@^1 motion@^12
```

Keep `package-lock.json` in version control.

## Minimum Project Structure

```text
src/
├── app/          # App, providers, router, routes, and QueryClient
├── components/
│   ├── layout/   # Ant Design application layout
│   ├── common/   # Shared Ant Design components
│   ├── ai/       # Ant Design X components
│   ├── charts/   # Ant Design Charts adapters
│   └── tables/   # Ant Design Table adapters
├── features/     # Domain modules added later
├── pages/        # Route-level pages
├── services/     # Axios client and API endpoints
├── hooks/        # TanStack Query hooks
├── types/        # Shared TypeScript types
├── theme/        # ConfigProvider theme
└── styles/       # Minimal global CSS
```

## Foundation Components

* `AppProviders` integrating React Router, `QueryClientProvider`, and Ant Design `ConfigProvider`.
* `AppShell` built with Ant Design.
* A `/` route and a `*` fallback route, without domain-specific routes.
* A shared Axios client using `VITE_API_BASE_URL`.
* A generic `DataTable` built with Ant Design Table.
* A reusable chart adapter built with Ant Design Charts.
* A domain-agnostic AI panel built with Ant Design X.
* Motion-based AI panel open and close transitions.
* A minimal `FoundationPage` confirming that all libraries are correctly integrated.