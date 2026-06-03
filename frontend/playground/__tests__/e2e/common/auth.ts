import type { Page } from '@playwright/test';

import { expect } from '@playwright/test';

export async function authLogin(page: Page) {
  // 确保登录表单正常 / Ensure login inputs are visible
  const usernameInput = await page.locator(`input[name='username']`);
  await expect(usernameInput).toBeVisible();

  const passwordInput = await page.locator(`input[name='password']`);
  await expect(passwordInput).toBeVisible();

  const sliderCaptcha = await page.locator(`div[name='captcha']`);
  const sliderCaptchaAction = await page.locator(`div[name='captcha-action']`);
  await expect(sliderCaptcha).toBeVisible();
  await expect(sliderCaptchaAction).toBeVisible();

  // 拖动验证码滑块 / Drag slider captcha
  // 获取拖动按钮的位置 / Locate drag handle
  const sliderCaptchaBox = await sliderCaptcha.boundingBox();
  if (!sliderCaptchaBox) throw new Error('滑块未找到');

  const actionBoundingBox = await sliderCaptchaAction.boundingBox();
  if (!actionBoundingBox) throw new Error('要拖动的按钮未找到');

  // 计算起始位置和目标位置 / Start and target pointer coords
  const startX = actionBoundingBox.x + actionBoundingBox.width / 2; // div 中心的 x 坐标 / handle center x
  const startY = actionBoundingBox.y + actionBoundingBox.height / 2; // div 中心的 y 坐标 / handle center y

  const targetX = startX + sliderCaptchaBox.width + actionBoundingBox.width; // 向右拖动容器的宽度 / drag by track width
  const targetY = startY; // y 坐标保持不变 / keep y

  // 模拟鼠标拖动 / Simulate mouse drag
  await page.mouse.move(startX, startY); // 移动到 action 的中心 / move to handle center
  await page.mouse.down(); // 按下鼠标 / mouse down
  await page.mouse.move(targetX, targetY, { steps: 20 }); // 拖动到目标位置 / drag to target
  await page.mouse.up(); // 松开鼠标 / mouse up

  // 在拖动后进行断言，检查action是否在预期位置, / Assert handle moved along x
  const newActionBoundingBox = await sliderCaptchaAction.boundingBox();
  expect(newActionBoundingBox?.x).toBeGreaterThan(actionBoundingBox.x);

  // 到这里已经校验成功，点击进行登录 / Submit login after captcha OK
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: 'login' }).click();
}
