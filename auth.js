const express = require('express');
const { body } = require('express-validator');
const { 
  register, 
  login, 
  getCurrentUser, 
  updateProfile, 
  changePassword,
  changeEmail
} = require('../controllers/authController');
const { getUsers } = require('../controllers/userController');
const { authenticateToken } = require('../middleware/auth');

const router = express.Router();

// 注册验证规则
const registerValidation = [
  body('username')
    .isLength({ min: 3, max: 50 })
    .withMessage('用户名长度应在3-50字符之间')
    .matches(/^[a-zA-Z0-9_]+$/)
    .withMessage('用户名只能包含字母、数字和下划线'),
  body('email')
    .isEmail()
    .withMessage('请输入有效的邮箱地址'),
  body('password')
    .isLength({ min: 6 })
    .withMessage('密码长度至少6位'),
  body('realName')
    .isLength({ min: 2, max: 50 })
    .withMessage('真实姓名长度应在2-50字符之间'),
  body('position')
    .notEmpty()
    .withMessage('职位不能为空'),
  body('dailyCost')
    .optional()
    .isFloat({ min: 0 })
    .withMessage('日成本必须为非负数')
];

// 登录验证规则
const loginValidation = [
  body('username')
    .notEmpty()
    .withMessage('用户名不能为空'),
  body('password')
    .notEmpty()
    .withMessage('密码不能为空')
];

// 更新资料验证规则
const updateProfileValidation = [
  body('realName')
    .optional()
    .isLength({ min: 2, max: 50 })
    .withMessage('真实姓名长度应在2-50字符之间'),
  body('phone')
    .optional()
    .matches(/^1[3-9]\d{9}$/)
    .withMessage('请输入有效的手机号码')
];

/**
 * 更改密码验证规则
 * - currentPassword: 必填，字符串
 * - newPassword: 必填，长度至少6位
 */
const changePasswordValidation = [
  body('currentPassword')
    .notEmpty().withMessage('当前密码不能为空'),
  body('newPassword')
    .isLength({ min: 6 }).withMessage('新密码长度至少6位')
];

/**
 * 更改邮箱验证规则
 * - newEmail: 必填，邮箱格式
 * - currentPassword: 必填，用于二次验证
 */
const changeEmailValidation = [
  body('newEmail')
    .isEmail().withMessage('请输入有效的邮箱地址'),
  body('currentPassword')
    .notEmpty().withMessage('当前密码不能为空')
];

// 路由定义
router.post('/register', registerValidation, register);
router.post('/login', loginValidation, login);
router.get('/me', authenticateToken, getCurrentUser);
router.put('/profile', authenticateToken, updateProfileValidation, updateProfile);

// 新增：更改密码与更改邮箱（需要登录）
router.post('/change-password', authenticateToken, changePasswordValidation, changePassword);
router.post('/change-email', authenticateToken, changeEmailValidation, changeEmail);

// 现有：获取用户列表（示例）
router.get('/users', authenticateToken, getUsers);

module.exports = router;
