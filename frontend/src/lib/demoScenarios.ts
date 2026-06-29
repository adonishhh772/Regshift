export interface DemoScenario {
  id: string;
  title: string;
  domain: string;
  text: string;
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: "procurement",
    title: "Procurement",
    domain: "procurement",
    text: "From next quarter, all purchase orders above £25,000 must require finance approval before supplier confirmation. The system must log who approved it and block confirmation if approval is missing.",
  },
  {
    id: "inventory",
    title: "Inventory",
    domain: "inventory",
    text: "Stock transfers above £10,000 must require warehouse manager approval before dispatch.",
  },
  {
    id: "finance",
    title: "Finance / Billing",
    domain: "finance_billing",
    text: "Customers must see total recurring charges, cancellation fees, and refund terms before invoice confirmation.",
  },
  {
    id: "hr",
    title: "HR / Compliance",
    domain: "hr_compliance",
    text: "Employees working over 48 hours per week must trigger a compliance warning and manager review.",
  },
  {
    id: "security",
    title: "Security",
    domain: "security",
    text: "Any role change granting financial permissions must be logged and reviewed by an administrator.",
  },
];

export const GOLDEN_DEMO_TEXT = DEMO_SCENARIOS[0].text;
