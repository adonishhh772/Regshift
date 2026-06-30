import { WorkspaceLayout } from "@/components/WorkspaceLayout";

export default function WorkspaceRouteLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <WorkspaceLayout>{children}</WorkspaceLayout>;
}
