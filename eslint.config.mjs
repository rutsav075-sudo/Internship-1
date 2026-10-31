import js from '@eslint/js';
import globals from 'globals';
export default [
  js.configs.recommended,
  {files:['app/static/app.js'], languageOptions:{ecmaVersion:2022,sourceType:'script',globals:globals.browser},
   rules:{eqeqeq:'error','no-var':'error','prefer-const':'error'}}
];
