import "../src/index.css";
import type { Preview } from "@storybook/react";
const preview: Preview = {
  parameters: {
    backgrounds: {
      default: "apple-light",
      values: [
        { name: "apple-light", value: "#ffffff" },
        { name: "apple-surface", value: "#f5f5f7" },
        { name: "apple-dark", value: "#1d1d1f" },
      ],
    },
  },
};
export default preview;
