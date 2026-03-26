import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "../components/ui/Button";

const meta: Meta<typeof Button> = {
  title: "UI/Button",
  component: Button,
  tags: ["autodocs"],
};
export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = { args: { variant: "primary", children: "Enregistrer" } };
export const Secondary: Story = { args: { variant: "secondary", children: "Annuler" } };
export const Danger: Story = { args: { variant: "danger", children: "Supprimer" } };
export const Ghost: Story = { args: { variant: "ghost", children: "Plus d'options" } };
export const Loading: Story = { args: { variant: "primary", loading: true, children: "Chargement" } };
