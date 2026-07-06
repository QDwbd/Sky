import logging

class Logger(object):
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }

    def __init__(self, filename, level='info', fmt='%(asctime)s - %(pathname)s [line:%(lineno)d] - %(levelname)s: %(message)s'):
        self.logger = logging.getLogger(filename)
        self.logger.setLevel(self.level_relations.get(level))
        
        # 清空已有 handlers，避免重复日志
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        format_str = logging.Formatter(fmt)

        # 屏幕输出
        sh = logging.StreamHandler()
        sh.setFormatter(format_str)
        self.logger.addHandler(sh)

        # 文件输出，覆盖旧文件
        fh = logging.FileHandler(filename, mode='w', encoding='utf-8')  # 'w' 模式覆盖
        fh.setFormatter(format_str)
        self.logger.addHandler(fh)

# 使用
log = Logger('run.log', level='debug')

if __name__ == '__main__':
    log.logger.debug('详细信息，调试使用')
    log.logger.info('正常信息')
    log.logger.warning('警告信息')
    log.logger.error('错误信息')
    log.logger.critical('问题很严重')
