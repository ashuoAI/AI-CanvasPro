const express = require('express');
const { body, param } = require('express-validator');
const { 
  getUsers, 
  getUser, 
  createUser,
  updateUser,
  deleteUser,
  resetPassword 
} = require('../controllers/userController');
const { 
  authenticateToken, 
  authorizeRoles 
} = require('../middleware/auth');

const router = express.Router();

// 用户创建验证规则
const userCreateValidation = [
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
  body('role')
    .optional()
    .isIn(['admin', 'manager', 'designer', 'pm'])
    .withMessage('用户角色无效'),
  body('dailyCost')
    .optional()
    .isFloat({ min: 0 })
    .withMessage('日成本必须为非负数'),
  body('phone')
    .optional({ nullable: true })
    .custom((value) => {
      if (value === null || value === undefined || value === '') {
        return true;
      }
      if (!/^1[3-9]\d{9}$/.test(value)) {
        throw new Error('请输入有效的手机号码');
      }
      return true;
    }),
  body('designLevelCoefficient')
    .optional()
    .isFloat({ min: 0.5, max: 2.0 })
    .withMessage('设计水平系数范围为0.50-2.00')
];

// 用户更新验证规则
const userUpdateValidation = [
  body('realName')
    .optional()
    .isLength({ min: 2, max: 50 })
    .withMessage('真实姓名长度应在2-50字符之间'),
  body('email')
    .optional()
    .isEmail()
    .withMessage('请输入有效的邮箱地址'),
  body('position')
    .optional()
    .notEmpty()
    .withMessage('职位不能为空'),
  body('role')
    .optional()
    .isIn(['admin', 'manager', 'designer', 'pm'])
    .withMessage('用户角色无效'),
  body('status')
    .optional()
    .isIn(['active', 'inactive'])
    .withMessage('用户状态无效'),
  body('dailyCost')
    .optional()
    .isFloat({ min: 0 })
    .withMessage('日成本必须为非负数'),
  body('phone')
    .optional({ nullable: true })
    .custom((value) => {
      if (value === null || value === undefined || value === '') {
        return true;
      }
      if (!/^1[3-9]\d{9}$/.test(value)) {
        throw new Error('请输入有效的手机号码');
      }
      return true;
    }),
  body('designLevelCoefficient')
    .optional()
    .isFloat({ min: 0.5, max: 2.0 })
    .withMessage('设计水平系数范围为0.50-2.00')
];

// ID参数验证
const idValidation = [
  param('id').isInt().withMessage('ID必须为整数')
];

// 所有路由都需要认证
router.use(authenticateToken);

// 路由定义
// 获取用户列表 - 所有认证用户都可以访问（用于下拉选择等）
router.get('/', getUsers);

// 创建用户 - 只有管理员可以访问
router.post('/', 
  authorizeRoles('admin'),
  userCreateValidation,
  createUser
);

// 获取用户详情 - 管理员和经理可以访问
router.get('/:id', 
  idValidation,
  authorizeRoles('admin', 'manager'),
  getUser
);

// 更新用户信息 - 只有管理员可以访问
router.put('/:id', 
  idValidation,
  authorizeRoles('admin'),
  userUpdateValidation,
  updateUser
);

// 删除用户 - 只有管理员可以访问
router.delete('/:id', 
  idValidation,
  authorizeRoles('admin'),
  deleteUser
);

// 重置用户密码为默认值 - 只有管理员可以访问
router.post('/:id/reset-password', 
  idValidation,
  authorizeRoles('admin'),
  resetPassword
);

module.exports = router;
