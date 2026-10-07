import { Fragment } from "react";
import { t } from "./index";

/**
 * Translation that can contain React elements, e.g. a bold name inside a sentence:
 *   <Trans k="portfolio.dialogs.deleteMessage" values={{ name: <strong>Main</strong>, count: 3 }} />
 * Plain (string/number) values are interpolated by t(); element values are inserted in place
 * of their {{placeholder}}.
 */
export default function Trans({ k, values = {} }) {
  const plain = {};
  const elements = {};
  for (const [name, value] of Object.entries(values)) {
    if (value !== null && typeof value === "object") elements[name] = value;
    else plain[name] = value;
  }
  const text = t(k, { ...plain, ...Object.fromEntries(Object.keys(elements).map((n) => [n, `{{${n}}}`])) });
  const parts = text.split(/(\{\{\w+\}\})/g);
  return (
    <>
      {parts.map((part, index) => {
        const name = part.match(/^\{\{(\w+)\}\}$/)?.[1];
        return <Fragment key={index}>{name && name in elements ? elements[name] : part}</Fragment>;
      })}
    </>
  );
}
