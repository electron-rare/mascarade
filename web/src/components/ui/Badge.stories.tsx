import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "../components/ui/Badge";

const meta: Meta<typeof Badge> = {
  title: "UI/Badge",
  component: Badge,
  tags: ["autodocs"],
};
export default meta;
type Story = StoryObj<typeof Badge>;

export const Accent: Story = { args: { color: "accent", children: "Active" } };
export const Error: Story = { args: { color: "error", children: "Failed" } };
export const Warning: Story = { args: { color: "warning", children: "Pending" } };
export const Muted: Story = { args: { color: "muted", children: "Draft" } };
