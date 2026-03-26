import type { Meta, StoryObj } from "@storybook/react";
import { Input } from "../components/ui/Input";

const meta: Meta<typeof Input> = {
  title: "UI/Input",
  component: Input,
  tags: ["autodocs"],
};
export default meta;
type Story = StoryObj<typeof Input>;

export const Default: Story = { args: { label: "Nom", placeholder: "Entrez votre nom" } };
export const WithValue: Story = { args: { label: "Email", value: "clement@lelectronrare.fr" } };
export const Disabled: Story = { args: { label: "Locked", value: "Non modifiable", disabled: true } };
