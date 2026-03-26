import type { Meta, StoryObj } from "@storybook/react";
import { Card, CardHeader } from "../components/ui/Card";

const meta: Meta<typeof Card> = {
  title: "UI/Card",
  component: Card,
  tags: ["autodocs"],
};
export default meta;
type Story = StoryObj<typeof Card>;

export const Default: Story = {
  args: { children: <div style={{ padding: "1rem" }}>Card content here</div> },
};

export const WithHeader: Story = {
  args: {
    children: (
      <>
        <CardHeader title="Agent Zero" subtitle="Coordination agent" />
        <div style={{ padding: "1rem" }}>Agent details and configuration</div>
      </>
    ),
  },
};
