import { defineConfig } from "tinacms";

// Blog editor for allheartsaflame.com. Posts are Markdown files in content/posts/; saving one commits it to GitHub,
// and the "Build blog" workflow turns it into a page on the site.
export default defineConfig({
  branch: "main",
  clientId: process.env.TINA_CLIENT_ID || "02d5b1d8-3e79-4a37-abb6-6289dd80e04c",
  token: process.env.TINA_TOKEN,

  build: { outputFolder: "admin", publicFolder: "." },
  media: { tina: { mediaRoot: "assets/images/blog", publicFolder: "." } },

  schema: {
    collections: [
      {
        name: "post",
        label: "Blog posts",
        path: "content/posts",
        format: "md",
        ui: {
          filename: { slugify: (values) => (values?.title || "post").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") },
        },
        fields: [
          { type: "string", name: "title", label: "Title", isTitle: true, required: true },
          { type: "datetime", name: "date", label: "Date", required: true },
          { type: "string", name: "excerpt", label: "Short summary (shown on the home page and in Facebook previews)", ui: { component: "textarea" } },
          { type: "image", name: "image", label: "Cover picture" },
          { type: "boolean", name: "draft", label: "Draft (keep hidden for now)" },
          { type: "rich-text", name: "body", label: "Post", isBody: true },
        ],
      },
    ],
  },
});
